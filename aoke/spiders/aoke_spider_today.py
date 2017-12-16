# -*- coding: utf-8 -*-
# import os
import scrapy
import pdb
import datetime, time

# 要查询赔率的公司
info_days = 1  # 1表示收集当天信息
ultimate_odds_num = 2   # 设定读取最后几个末尾赔率进行比较
# 算法思想：
# 比较澳门的终盘赔率与这时必发的赔率，选取澳门相对较低的方向
# 优化方案
# 1.读取多个澳门末尾赔率（设定一个参数）可能3比较合适
# 同样的方法对多个澳门：必发赔率对比较，若结果相同则选取，否则不选
# 2 判断盘口
# ①若盘口不同，直接选取澳门方向
# ②若盘口不同，若满足澳门方向赔率《2.0 则选取澳门方向，否则不选
# 3 判段水位差距
# 水位差距达到一定程度才表示支持方向 比如》0.05
# 4 赛前时间判断
# 若澳门终盘赛前时间（minutes）> 540 （可设定为一个参数）则放弃

bookmakerID = 84
bookmakerID2 = 19
# 50 pinnacle, 250 皇冠 84 澳门 19 必发交易所

# core 算法判断参数
limit_price_differ = 0.1  # 达到支持所需要的水位差距
low_handicap_price = 1.8  # 升盘后的水位所限制的最小值
high_handicap_price = 2.0  # 升盘后的水位所限制的最大值
ultimate_price_change = 0.08  # 最终水位变化限制

# 盘口字典
handicap_dict = {
    '平手': 0.0,
    '平手/半球': 0.25,
    '半球': 0.5,
    '半球/一球': 0.75,
    '一球': 1.0,
    '一球/球半': 1.25,
    '球半': 1.5,
    '球半/两球': 1.75,
    '两球': 2.0,
    '两球/两球半': 2.25,
    '两球半': 2.5,
    '两球半/三球': 2.75,
    '三球': 3.0,
    '三球/三球半': 3.25,
    '三球半': 3.5,
    '三球半/四球': 3.75,
    '四球': 4.0,
    '四球/四球半': 4.25,
    '四球半': 4.5,
    '四球半/五球': 4.75,
    '五球': 5.0
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
    if net_handicap >= 1.0:
        net_handicap = 1.0
    elif net_handicap <= -1.0:
        net_handicap = -1.0
    else:
        net_handicap = net_handicap * 2
    # 有时候会超过边界
    if net_handicap < -1:
        net_handicap = -1
    if net_handicap > 1:
        net_handicap = 1
    return net_handicap


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
        change_handicap = current_handicap - prev_handicap
        if (change_handicap) > 0:
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
    match_id = scrapy.Field()  # 比赛唯一ID
    host = scrapy.Field()  # 主队名称
    guest = scrapy.Field()  # 客队名称
    league_name = scrapy.Field()  # 联赛名
    start_time = scrapy.Field()  # 开始时间
    host_goal = scrapy.Field()  # 主队进球数
    guest_goal = scrapy.Field()  # 客队进球数
    is_end = scrapy.Field()  # 比赛是否已结束
    # 关于赔率
    macao_handicap = scrapy.Field()  # pinnacle 初始盘口名
    macaoBifa_support_direction = scrapy.Field()  # 该算法支持方向
    algorithm_score = scrapy.Field()  # 根据赛果评判算法，赢全+1，赢半+0.5 输同理


class SoccerSpider(scrapy.Spider):
    name = 'aoke_spider_today'
    allowed_domains = ['www.okooo.com']
    nowadays = datetime.datetime.now().strftime("%Y-%m-%d")  # 获取当前日期
    # tomorrow = (datetime.datetime.now()+datetime.timedelta(days = +1)).strftime("%Y-%m-%d")     # 获取明天日期
    # 生成遍历的日期列表
    calendar_list = []
    # 遍历一年的数据
    for i in range(info_days):
        add_day = (datetime.datetime.now() + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        add_url = "http://www.okooo.com/livecenter/football/?date=" + add_day
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
                start_time = response.css('td[class=match_date]').xpath('text()').extract()[0].split('-')[0] + '-' + \
                             tr.xpath('td')[2].xpath('text()').extract()[0]
                # 主进球
                host_goal_text = tr.xpath('td[@class="show_score"]/a/b')[0].xpath('text()').extract()
                if len(host_goal_text) == 0:
                    host_goal = 0
                else:
                    host_goal = int(host_goal_text[0])
                # 客进球
                guest_goal_text = tr.xpath('td[@class="show_score"]/a/b')[2].xpath('text()').extract()
                if len(guest_goal_text) == 0:
                    guest_goal = 0
                else:
                    guest_goal = int(guest_goal_text[0])
                # 判断是否完场
                get_if_end = tr.xpath('td')[3].xpath('span/text()').extract()
                if len(get_if_end) > 0 and get_if_end[0] == '完':
                    is_end = True
                else:
                    is_end = False
                # 想要爬取赔率的公司ID
                bookmaker_id = bookmakerID
                match_url = 'http://www.okooo.com/soccer/match/' + match_id + '/ah/change/' + str(bookmaker_id)
                yield scrapy.Request(match_url, meta={'match_id': match_id, 'host': host_name, 'guest': guest_name,
                                                      'start_time': start_time, 'host_goal': host_goal,
                                                      'guest_goal': guest_goal, 'is_end': is_end,
                                                      'league_name': league_name}, callback=self.match_macao_parse)

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
        return float(price)
    # 将赛前时间转化为赛前多少分钟
    def preTime2num(self, pre_time):
        try:
            hour = int(pre_time[2:5])
        except:
            hour = int(pre_time[2:4])
        # 分钟时间有的在5:7，有的在6:8
        try:
            min = int(pre_time[5:7])
        except:
            min = int(pre_time[6:8])
        pre_time_num = hour*60 + min
        return pre_time_num

    def match_macao_parse(self, response):
        handle_httpstatus_list = [404]
        if response.status in handle_httpstatus_list:
            print('访问404')
            return False
        odds_tr_len = len(response.xpath('//tbody')[0].xpath('tr')) - 2
        if odds_tr_len <= 0:
            return False
        # 如果澳门赔率数目小于给定的参数，那么就改变参数为澳门赔率数目
        if (odds_tr_len - ultimate_odds_num) < 0:
            reality_ultimate_odds_num = odds_tr_len
        else:
            reality_ultimate_odds_num = ultimate_odds_num
        macao_ultimate_info = []    # 保存澳门末尾赔率信息的列表，长度由reality_ultimate_odds_num参数控制
        # 获取澳门末尾赔率，根据reality_ultimate_odds_num 参数值获取倒数几个
        for i in range(reality_ultimate_odds_num):
            tr_index = i + 2    # 中盘赔率开始的index,有两个tr是头部需要跳过
            temp_macao_info_dict = {}
            macao_ultimate_handicap = response.xpath('//tbody')[0].xpath('tr')[tr_index].xpath('td')[3].xpath('text()').extract()[0]
            macao_time = response.xpath('//tbody')[0].xpath('tr')[tr_index].xpath('td')[1].xpath('text()').extract()[0]  # 澳门终盘的赛前时间
            macao_host_price = self.find_odds(response.xpath('//tbody')[0].xpath('tr')[tr_index], 'host')  # 终盘主赔
            macao_guest_price = self.find_odds(response.xpath('//tbody')[0].xpath('tr')[tr_index], 'guest')  # 终盘客赔
            temp_macao_info_dict['macao_handicap'] = macao_ultimate_handicap
            temp_macao_info_dict['macao_time'] = macao_time
            temp_macao_info_dict['macao_host_price'] = macao_host_price
            temp_macao_info_dict['macao_guest_price'] = macao_guest_price
            macao_ultimate_info.append(temp_macao_info_dict)


        bookmaker_id = bookmakerID2
        match_url = 'http://www.okooo.com/soccer/match/' + response.meta['match_id'] + '/ah/change/' + str(bookmaker_id)
        yield scrapy.Request(match_url, meta={'match_id': response.meta['match_id'], 'host': response.meta['host'], 'guest': response.meta['guest'],
                                              'start_time': response.meta['start_time'], 'host_goal': response.meta['host_goal'],
                                              'guest_goal': response.meta['guest_goal'], 'is_end': response.meta['is_end'],
                                              'league_name': response.meta['league_name'], 'macao_ultimate_info':macao_ultimate_info,
                                              'reality_ultimate_odds_num':reality_ultimate_odds_num}, callback=self.match_bifa_parse)

    def match_bifa_parse(self, response):
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
        support_direction_list = []  # 支持方向列表（因为对比了多个末尾赔率)
        for i in range(response.meta['reality_ultimate_odds_num']):
            support_direction_list.append(0)    # 添加默认值0
        support_direction = 0   # 最终支持方向 1 0 -1 分别表示主队，中立，客队
        match_algorithm_score = 0  # 本场算法评分
        ultimate_handicap = ''  # 用来评分
        count = 0
        for macao_ultimate_info in response.meta['macao_ultimate_info']:
            macao_time = macao_ultimate_info['macao_time']
            macao_host = macao_ultimate_info['macao_host_price']
            macao_guest = macao_ultimate_info['macao_guest_price']
            macao_ultimate_handicap = macao_ultimate_info['macao_handicap']
            macao_pre_comp_time_num = self.preTime2num(macao_time)
            if count == 0:
                ultimate_handicap = macao_ultimate_handicap

            # 遍历赔率
            odds_tr_len = len(response.xpath('//tbody')[0].xpath('tr'))
            sub_count = odds_tr_len
            for i in range(odds_tr_len):
                # 跳过表格头(有两个tr不是赔率)
                if sub_count <= 2:
                    break
                    # 从末尾到头遍历赔率tr
                current_pre_comp_time = response.xpath('//tbody')[0].xpath('tr')[sub_count-1].xpath('td')[1].xpath('text()').extract()[0]  # 澳门初盘的赛前时间
                current_pre_comp_time_num = self.preTime2num(current_pre_comp_time)
                # 如果当前赛前时间小于澳门初盘的赛前时间，对赔率进行比较，找到澳门-必发 较小的的方向
                if current_pre_comp_time_num <= macao_pre_comp_time_num:
                    current_host_price = self.find_odds(response.xpath('//tbody')[0].xpath('tr')[sub_count-1], 'host')  # 当前主队赔率
                    current_guest_price = self.find_odds(response.xpath('//tbody')[0].xpath('tr')[sub_count-1], 'guest')  # 当前客队赔率
                    # 计算澳门与必发之差
                    host_gap =  macao_host - current_host_price
                    guest_gap =  macao_guest - current_guest_price
                    # 选取较小的方向
                    if (host_gap<0 and guest_gap<0) or (host_gap>0 and guest_gap>0):
                        if (host_gap - guest_gap) < 0:
                            support_direction_list[count] = 1
                        elif (host_gap - guest_gap) > 0:
                            support_direction_list[count] = -1
                    elif host_gap!=0 or guest_gap!=0:
                        if host_gap<0:
                            support_direction_list[count] = 1
                        elif guest_gap<0:
                            support_direction_list[count] = -1
                    break
                sub_count -= 1
            count += 1
        # 遍历suppoer_direction_list
        support_host = True
        support_guest = True
        # 判断是否支持主队
        for singleSupport in support_direction_list:
            if singleSupport < 0:
                support_host = False
        # 判断是否支持客队
        for singleSupport in support_direction_list:
            if singleSupport > 0:
                support_guest = False
                # 初步评分
        # 判断suppor
        if (support_host and support_guest) or (not support_host and not support_guest):
            support_direction = 0
        else:
            if support_host:
                support_direction = 1
            else:
                support_direction = -1

        # 初步评分
        ultimate_handicap_num = handicap2num(ultimate_handicap)
        host_net_goal = single_match_Item['host_goal'] - single_match_Item['guest_goal']  # 主队净胜球
        net_handicap = score_my_algorithm(float(host_net_goal), ultimate_handicap_num)
        # mid = single_match_Item['match_id']
        # if mid == 945076 or mid == '945076':
        #     a = 1
        #     pdb.set_trace()
        # 根据判断方向给出本轮比赛算法最终得分
        if support_direction == 1:
            match_algorithm_score = net_handicap
        elif support_direction == -1:
            match_algorithm_score = -net_handicap
        single_match_Item['macao_handicap'] = ultimate_handicap
        single_match_Item['macaoBifa_support_direction'] = support_direction  # 该算法支持方向
        single_match_Item['algorithm_score'] = match_algorithm_score  # 该算法本场比赛评分
        yield single_match_Item