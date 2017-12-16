# -*- coding: utf-8 -*-
# import os
import scrapy
import pdb
import datetime, time

# core 算法判断参数
limit_change_price = 0.10   # 要求降水变化需要达到的水位
limit_max_price = 2.0       # 要求不能高于的水位

# 盘口字典
handicap_dict = {
    '平手':0,
    '平手/半球':0.25,
    '半球':0.5,
    '半球/一球':0.75,
    '一球':1,
    '一球/球半':1.25,
    '球半':1.5,
    '球半/两球':1.75,
    '两球':2,
    '两球/两球半':2.25,
    '两球半':2.5,
    '两球半/三球':2.75,
    '三球':3,
    '三球/三球半':3.25,
    '三球半':3.5,
    '三球半/四球':3.75,
    '四球':4,
    '四球/四球半':4.25,
    '四球半':4.5,
    '四球半/五球':4.75,
    '五球':5
}

# 升降盘判断函数
def compare_handicap(prev, current):
    result = 0
    if prev != current:
        # 转换 prev 盘口到数字
        if prev[0] == '受':
            prev_handicap = -handicap_dict[prev[1:]]
        else:
            prev_handicap = handicap_dict[prev]
        if current[0] == '受':
            current_handicap = -handicap_dict[current[1:]]
        else:
            current_handicap = handicap_dict[current]
        # 判断升降盘
        if (current_handicap - prev_handicap) > 0:
            result = 1
        else:
            result = -1
    return result

# 处理赔率格式
def get_handicap_odds(price_text):
    if len(price_text) == 4:
        price_float = float(price_text)  # 主队赔率
    else:
        price_float = float(price_text[:-1])  # 主队赔率
    return price_float

# 比赛item
class match_Item(scrapy.Item):
    match_id = scrapy.Field()    # 比赛唯一ID
    host = scrapy.Field()       # 主队名称
    guest = scrapy.Field()      # 客队名称
    league_name = scrapy.Field()  # 联赛名
    start_time = scrapy.Field()  # 开始时间
    host_goal = scrapy.Field() # 主队进球数
    guest_goal = scrapy.Field() # 客队进球数
    is_end = scrapy.Field()  # 比赛是否已结束
    # 关于赔率
    pinnacle_handicap = scrapy.Field()    # pinnacle 初始盘口名
    pinnacle_support_direction = scrapy.Field()   # 该算法支持方向


class SoccerSpider(scrapy.Spider):
    name = 'aoke_pinnacle'
    allowed_domains = ['www.okooo.com']
    nowadays = datetime.datetime.now().strftime("%Y-%m-%d")   # 获取当前日期
    # tomorrow = (datetime.datetime.now()+datetime.timedelta(days = +1)).strftime("%Y-%m-%d")     # 获取明天日期
    start_urls = [
        "http://www.okooo.com/livecenter/football/?date="+nowadays
    ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url)


    def parse(self, response):
        for tr in response.css('div[id=livescore_table]').css('tr'):
            if len(tr.xpath('@id')) > 0:
                # 唯一比赛ID
                match_id = tr.xpath('@id').extract()[0].split('_')[-1]
                league_name = tr.xpath('@type').extract()[0]
                host_name = tr.xpath('td/a[@class="ctrl_homename"]/text()').extract()[0]
                guest_name = tr.xpath('td/a[@class="ctrl_awayname"]/text()').extract()[0]
                start_time = response.css('td[class=match_date]').xpath('text()').extract()[0].split('-')[0]+'-'+ tr.xpath('td')[2].xpath('text()').extract()[0]
                # 主进球
                host_goal_text = tr.xpath('td[@class="show_score"]/a/b')[0].xpath('text()').extract()
                if len(host_goal_text)==0:
                    host_goal = 0
                else:
                    host_goal = int(host_goal_text[0])
                # 客进球
                guest_goal_text = tr.xpath('td[@class="show_score"]/a/b')[2].xpath('text()').extract()
                if len(guest_goal_text)==0:
                    guest_goal = 0
                else:
                    guest_goal = int(guest_goal_text[0])
                # 判断是否完场
                get_if_end = tr.xpath('td')[3].xpath('span/text()').extract()
                if len(get_if_end) >0 and get_if_end[0] == '完':
                    is_end = True
                else:
                    is_end = False
                # 想要爬取赔率的公司ID
                bookmaker_id = 50
                match_url = 'http://www.okooo.com/soccer/match/'+match_id+'/ah/change/' + str(bookmaker_id)
                yield scrapy.Request(match_url, meta={'match_id': match_id, 'host': host_name, 'guest': guest_name, 'start_time': start_time, 'host_goal': host_goal,
                                         'guest_goal': guest_goal, 'is_end': is_end, 'league_name': league_name},callback=self.match_parse)


    def match_parse(self, response):
        # handle_httpstatus_list = [404]
        # if response.status in handle_httpstatus_list:
        #     print('访问404')
        #     return False
        # 声明match对象，保存当前比赛数据
        single_match_Item = match_Item()
        single_match_Item['match_id'] = response.meta['match_id']
        single_match_Item['host'] = response.meta['host']
        single_match_Item['guest'] = response.meta['guest']
        single_match_Item['start_time'] = response.meta['start_time']
        single_match_Item['host_goal'] = response.meta['host_goal']
        single_match_Item['guest_goal'] = response.meta['guest_goal']
        single_match_Item['is_end'] = response.meta['is_end']
        single_match_Item['league_name'] = response.meta['league_name']

        # core算法重要记录指标
        support_direction = 0   # 支持方向 1 0 -1 分别表示主队，中立，客队
        if_change_handicap = 0 # 记录盘口是否变化
        satisfy_change_price_host = False # 记录是否已经达到降水要求
        satisfy_change_price_guest = False # 记录是否已经达到降水要求
        original_host_price = 0.0   # 初盘主赔率
        original_handicap_name = '' # 初盘盘口
        original_guest_price = 0.0  # 初盘客赔率
        # 遍历赔率
        odds_tr_len = len(response.xpath('//tbody')[0].xpath('tr'))
        count = odds_tr_len
        for i in range(odds_tr_len):
            # 跳过表格头(有两个tr不是赔率)
            if count<=2:
                break
            # 从末尾到头遍历赔率tr

            # 当便利到倒数第二个开始与之前那个赔率比较
            if count<odds_tr_len:
                prev_tr = response.xpath('//tbody')[0].xpath('tr')[count]
                prev_handicap_name = prev_tr.xpath('td')[3].xpath('text()').extract()[0]  # 之前盘口名称
            current_tr = response.xpath('//tbody')[0].xpath('tr')[count-1]
            # pre_start_time = current_tr.xpath('td')[1].xpath('text()').extract()[0] # 赛前时间
            # 非常坑爹的一个地方，有时候赔率会在两个span下
            if len(current_tr.xpath('td')[2].xpath('span/span')) > 0:
                # 有时候最后会有上升下降符号
                host_price = get_handicap_odds(current_tr.xpath('td')[2].xpath('span/span/text()').extract()[0])  # 主队赔率
            else:
                host_price = get_handicap_odds(current_tr.xpath('td')[2].xpath('span/text()').extract()[0])    # 主队赔率
            if len(current_tr.xpath('td')[4].xpath('span/span')) > 0:
                guest_price = get_handicap_odds(current_tr.xpath('td')[4].xpath('span/span/text()').extract()[0])  # 客队赔率
            else:
                guest_price = get_handicap_odds(current_tr.xpath('td')[4].xpath('span/text()').extract()[0])    # 客队赔率
            handicap_name = current_tr.xpath('td')[3].xpath('text()').extract()[0]  # 盘口名称

            # 开始core算法
            # 记录初始赔率,初始盘口
            if count == odds_tr_len:
                original_host_price = host_price
                original_handicap_name = handicap_name
                original_guest_price = guest_price

            # 记录盘口是否变化，变化还根据1 和 -1 取分主升盘还是降盘, 0表示不变
            if (count < odds_tr_len) and support_direction == 0:
                if_change_handicap = compare_handicap(prev_handicap_name,handicap_name)

            # mid = single_match_Item['match_id']
            # if mid == 953813 or mid == 962219:
            #     pdb.set_trace()

            # 判断是否相对初盘下降了要求的水位，并且对赔率有约束条件不能太高
            # 取最先达到的降水方向置True, 接下来不能更改
            if (host_price-original_host_price)<=(-limit_change_price) and host_price<limit_max_price and not satisfy_change_price_guest and support_direction!=101:
                satisfy_change_price_host = True
            if (guest_price-original_guest_price)<=(-limit_change_price) and guest_price<limit_max_price and not satisfy_change_price_host and support_direction!=101:
                satisfy_change_price_guest = True

            # 根据盘口是否变化执行不同操作
            if if_change_handicap != 0 and support_direction == 0:
                # 如果之前已经达到降水要求且盘口变化相同则 对该方向利好, 相反则反向
                if (satisfy_change_price_host and if_change_handicap == 1) or (satisfy_change_price_guest and if_change_handicap == -1):
                    support_direction = if_change_handicap
                elif (satisfy_change_price_host and if_change_handicap == -1) or (satisfy_change_price_guest and if_change_handicap == 1):
                    support_direction = -if_change_handicap
                # 如果在达到水位下降条件之前变盘，将support_direction置为 101 表示不再看本场比赛
                else:
                    support_direction = 101
            count -= 1
        # 如果到最后达到降水条件的公司还没有在该方向上升盘，且suppor_direction仍为0则 置support_direction为达到降水条件的反方向
        if time.time() - time.mktime(time.strptime(single_match_Item['start_time'],'%Y-%m-%d %H:%M')) > -60:
            if satisfy_change_price_host and support_direction == 0:
                support_direction = -1
            if satisfy_change_price_guest and support_direction == 0:
                support_direction = 1
        single_match_Item['pinnacle_handicap'] = original_handicap_name
        single_match_Item['pinnacle_support_direction'] = support_direction  # 该算法支持方向
        yield single_match_Item