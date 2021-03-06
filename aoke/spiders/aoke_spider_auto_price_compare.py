# -*- coding: utf-8 -*-
# import os
import scrapy
import pdb
import datetime, time

# 要查询赔率的公司
info_days = 3 # 收集多少天的信息
bookmakerID = 84
# 50 pinnacle, 250 皇冠 84 澳门

# core 算法判断参数
limit_time_hour = 1    # 限制临场最近小时数
limit_price_differ = 0.1    # 达到支持所需要的水位差距

# 盘口字典
handicap_dict = {
    '平手':0.0,
    '平手/半球':0.25,
    '半球':0.5,
    '半球/一球':0.75,
    '一球':1.0,
    '一球/球半':1.25,
    '球半':1.5,
    '球半/两球':1.75,
    '两球':2.0,
    '两球/两球半':2.25,
    '两球半':2.5,
    '两球半/三球':2.75,
    '三球':3.0,
    '三球/三球半':3.25,
    '三球半':3.5,
    '三球半/四球':3.75,
    '四球':4.0,
    '四球/四球半':4.25,
    '四球半':4.5,
    '四球半/五球':4.75,
    '五球':5.0
}


# 转换盘口到数字
def handicap2num(handicap_name):
    if handicap_name[0] == '受':
        result = -handicap_dict[handicap_name[1:]]
    else:
        result = handicap_dict[handicap_name]
    return result

# 根据净胜球和盘口计算盘口赛果 返回值：0 0.5 1 -0.5 -1
def score_my_algorithm(net_score, handicap):
    net_handicap = net_score - handicap
    if net_handicap > 1.0:
        net_handicap = 1.0
    elif net_handicap < -1.0:
        net_handicap = -1.0
    return net_handicap

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
    algorithm_score = scrapy.Field()   # 根据赛果评判算法，赢全+1，赢半+0.5 输同理


class SoccerSpider(scrapy.Spider):
    name = 'aoke_price'
    allowed_domains = ['www.okooo.com']
    nowadays = datetime.datetime.now().strftime("%Y-%m-%d")   # 获取当前日期
    # tomorrow = (datetime.datetime.now()+datetime.timedelta(days = +1)).strftime("%Y-%m-%d")     # 获取明天日期
    # 生成遍历的日期列表
    calendar_list = []
    # 遍历一年的数据
    for i in range(info_days):
        add_day = (datetime.datetime.now()+datetime.timedelta(days = -(i+1))).strftime("%Y-%m-%d")
        add_url = "http://www.okooo.com/livecenter/football/?date="+add_day
        calendar_list.append(add_url)
    start_urls = calendar_list

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
                bookmaker_id = bookmakerID
                match_url = 'http://www.okooo.com/soccer/match/'+match_id+'/ah/change/' + str(bookmaker_id)
                yield scrapy.Request(match_url, meta={'match_id': match_id, 'host': host_name, 'guest': guest_name, 'start_time': start_time, 'host_goal': host_goal,
                                         'guest_goal': guest_goal, 'is_end': is_end, 'league_name': league_name},callback=self.match_parse)
    # 需要当前查询到的tr，还有host / guest
    def find_odds(self, tr, hg):
        # 根据主客不同，赔率所在td位置不同
        if hg == 'host':
            td_index = 2
        else:
            td_index = 4
        # 有时候赔率会在td下又一个span内,或者又一个span
        # 先查看tr 下有无赔率
        price_text = tr.xpath('td')[td_index].xpath('text()')
        # 如果=0则继续查找 tr span 下
        if len(price_text) == 0:
            price_text = tr.xpath('td')[td_index].xpath('span/text()')
            # 如果还是等于0 那继续查找 tr span span 下
            if len(price_text) == 0:
                price_text = tr.xpath('td')[td_index].xpath('span/span/text()')
        price = price_text.extract()[0][:4]
        return price

    def match_parse(self, response):
        handle_httpstatus_list = [404]
        if response.status in handle_httpstatus_list:
            print('访问404')
            return False
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
        match_algorithm_score = 0   # 本场算法评分
        original_host_price = 0.0   # 初盘主赔率
        original_handicap_name = '' # 终盘盘口
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
                prev_host_price = self.find_odds(prev_tr, 'host')
                prev_guest_price = self.find_odds(prev_tr, 'guest')

            current_tr = response.xpath('//tbody')[0].xpath('tr')[count-1]
            pre_start_time = current_tr.xpath('td')[1].xpath('text()').extract()[0] # 赛前时间
            # 将赛前时间转化为数字
            pre_start_time_hour = int(pre_start_time[2:4])
            # pre_start_time_minute = int(pre_start_time[5:7])

            # 记录终盘
            if count == odds_tr_len:
                original_handicap_name = response.xpath('//tbody')[0].xpath('tr')[3].xpath('td')[3].xpath('text()').extract()[0]
                handicap_num = handicap2num(original_handicap_name)
                host_net_goal = single_match_Item['host_goal'] - single_match_Item['guest_goal']    # 主队净胜球
                net_handicap = score_my_algorithm(float(host_net_goal),handicap_num)
                
            # 到达临场限制时间开始分析支持方向
            if pre_start_time_hour < limit_time_hour:
                # 如果第一个倒计时时间就满足的情况
                if count == odds_tr_len:
                    prev_host_price = self.find_odds(current_tr, 'host')
                    prev_guest_price = self.find_odds(current_tr, 'guest')
                if abs(float(prev_host_price) - float(prev_guest_price)) >= limit_price_differ:
                    if float(prev_host_price) < float(prev_guest_price):
                        support_direction = 1
                        match_algorithm_score = net_handicap
                    else:
                        support_direction = -1
                        match_algorithm_score = -net_handicap
                break
            count -= 1
        single_match_Item['pinnacle_handicap'] = original_handicap_name
        single_match_Item['pinnacle_support_direction'] = support_direction  # 该算法支持方向
        single_match_Item['algorithm_score'] = match_algorithm_score  # 该算法本场比赛评分
        yield single_match_Item