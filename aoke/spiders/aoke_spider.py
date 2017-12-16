# -*- coding: utf-8 -*-
# import os
import scrapy
import pdb
import datetime, time
import re
import json


# 要查询赔率的公司
info_days = 1  # 收集多少天的信息  1表示当天分析
# 对于以下参数的统计：
# changePrice = 0.08  # 变盘增减水位
# pass_price = 0.15 # 水位下降通过线，通过则支持《
# 712 天 84 523 3046 23612 select_league_list = ['西甲','德甲','苏超','友谊赛','澳超','荷甲','荷乙','美联']
# 712 天 160.5 3079 23612 全部
# 1800 天 74 1197 7088 51072 select_league_list = ['西甲','德甲','苏超','友谊赛','澳超','荷甲','荷乙','美联'] 盈利率:0.062 命中率:53.1%
# 凯利公式计算投注比例(以赔率为1.9)：0.284 相对来说0.284/0.273=1.04,即select_list列表中投注注码应该为全部联赛的1.04倍
# 1800 天 331 6923 51072 全部 盈利率:0.048 命中率:52.4%
# 凯利公式计算投注比例(以赔率为1.9)：0.273

bookmakerID = 84
# 50 pinnacle, 250 皇冠 84 澳门 19 必发交易所
# 算法思想
# 1.遍历澳门变赔找出变盘后水位大幅下降的方向，若一场比赛有多个方向，则一致才表示支持，否则放弃    √
# 可能的优化方向
# 1 看好方向要与初盘让盘方向一致，平/半为基准
# 2 排除没变盘一次降水》0.15的方向

# 选取的联赛列表
select_league_list = ['西甲','德甲','苏超','友谊赛','澳超','荷甲','荷乙','美联']
# 算法判断参数
changePrice = 0.08  # 变盘增减水位
pass_price = 0.15 # 水位下降通过线，通过则支持《

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

# 判断主队是否让盘
def judge_host_advantage(begin_handicap):
    # 转换盘口到数字
    result = 0
    if begin_handicap[0] == '受':
        begin_handicap_num = -handicap_dict[begin_handicap[1:]]
    else:
        begin_handicap_num = handicap_dict[begin_handicap]
    if begin_handicap_num > 0.25:
        result = 1
    elif begin_handicap_num < 0.25:
        result = -1
    return result   # 1

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
        if abs(change_handicap) <= 0.25:
            if change_handicap > 0:
                result = 1
            elif change_handicap < 0:
                result = -1
    return result

# 升降盘计算函数
def calculate_handicap(prev, current):
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
        result = current_handicap - prev_handicap
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
    macao_support_direction = scrapy.Field()  # 该算法支持方向
    algorithm_score = scrapy.Field()  # 根据赛果评判算法，赢全+1，赢半+0.5 输同理


class SoccerSpider(scrapy.Spider):
    name = 'aoke'
    allowed_domains = ['www.okooo.com']
    nowadays = datetime.datetime.now().strftime("%Y-%m-%d")  # 获取当前日期
    # tomorrow = (datetime.datetime.now()+datetime.timedelta(days = +1)).strftime("%Y-%m-%d")     # 获取明天日期
    # 生成遍历的日期列表
    calendar_list = []
    # 遍历一年的数据
    for i in range(info_days):
        if info_days == 1:
            add_day = (datetime.datetime.now() + datetime.timedelta(days=i)).strftime("%Y-%m-%d")   # info_days == 1 表示获取当天分析
        else:
            add_day = (datetime.datetime.now() + datetime.timedelta(days=-(i + 1))).strftime("%Y-%m-%d")
        add_url = "http://www.okooo.com/livecenter/football/?date=" + add_day
        calendar_list.append(add_url)
    start_urls = calendar_list

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url)

    def parse(self, response):
        # 获取进球数据,并保存在本类中，供最后读取使用
        # self.get_goal_info = json.loads(re.findall(r"{.*]}{1}",response.xpath('//script/text()').extract()[2])[0])

        for tr in response.css('div[id=livescore_table]').css('tr'):
            if len(tr.xpath('@id')) > 0:
                # 唯一比赛ID
                match_id = tr.xpath('@id').extract()[0].split('_')[-1]
                league_name = tr.xpath('@type').extract()[0]
                host_name = tr.xpath('td/a[@class="ctrl_homename"]/text()').extract()[0]
                guest_name = tr.xpath('td/a[@class="ctrl_awayname"]/text()').extract()[0]
                start_time = response.css('td[class=match_date]').xpath('text()').extract()[0].split('-')[0] + '-' + \
                             tr.xpath('td')[2].xpath('text()').extract()[0]
                # if not league_name in select_league_list:
                #     continue

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
                if len(get_if_end) > 0 and (get_if_end[0] == '完' or get_if_end[0] == '加时完' or get_if_end[0] == '点球完'):
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
    # 将多个support统一化
    # 若不一致则取0
    def unification_support(self,support_direction,last_change_support,begin_to_ultimate_handicap_change):
        # 最重要的是support_direction，last_change_support
        # begin_to_ultimate_handicap_change 起参考作用
        if support_direction == last_change_support:
            result = support_direction
        else:
            result = support_direction + last_change_support
        if (result != begin_to_ultimate_handicap_change) and result != 0:
            result = result + begin_to_ultimate_handicap_change
        return result

    # 先获取澳门赔率
    def match_macao_parse(self, response):
        handle_httpstatus_list = [404]
        if response.status in handle_httpstatus_list:
            print('访问404')
            return False
        odds_tr_len = len(response.xpath('//tbody')[0].xpath('tr')) - 2
        if odds_tr_len <= 0:
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

        # 思想：找到澳门初盘到终盘升降两个盘口方向为support
        handicap_change_support_list = [] # 记录盘口变化水位比较导致的支持列表
        pre_handicap = '' # 保存前面查找的盘口
        pre_host_price = '' # 保存前面host price
        pre_guest_price = '' # 保存前面guest price
        # 终盘
        ultimate_handicap = ''
        ultimate_host = 0
        ultimate_guest = 0
        # 初盘
        begin_handicap = ''
        begin_host = 0
        begin_guest = 0

        tr_len = len(response.xpath('//tbody')[0].xpath('tr[@class=""]'))
        special_price = False   # 若出现特殊赔率就跳过该场
        count = 0
        for tr in response.xpath('//tbody')[0].xpath('tr[@class=""]'):
            current_handicap = tr.xpath('td')[3].xpath('text()').extract()[0]
            current_host_price = float(self.find_odds(tr, 'host'))
            current_guest_price = float(self.find_odds(tr, 'guest'))
            # 有时候澳门赔率会出现特殊情况，特别大、特别小的情况要排除
            if current_host_price > 2.15 or current_guest_price > 2.15 or current_host_price < 1.7 or current_guest_price < 1.7:
                special_price = True
                break
            # 终盘
            if count == 0:
                ultimate_handicap = current_handicap
                ultimate_host = current_host_price
                ultimate_guest = current_guest_price
            # 初盘
            if count == tr_len - 1:
                begin_handicap = current_handicap
                begin_host = current_host_price
                begin_guest = current_guest_price
            if pre_handicap != '':
                if current_handicap != pre_handicap:
                    # 因为是倒向遍历，所以pre - current
                    handicap_differ = calculate_handicap(current_handicap,pre_handicap)
                    normal_host_price = current_host_price + (handicap_differ / 0.25) * changePrice  # 按照降盘水位应该达到的主价格值
                    normal_guest_price = current_guest_price + (handicap_differ / 0.25) * -changePrice  # 按照降盘水位应该达到的客价格值
                    # 临时支持方向
                    temp_support_direction = 0
                    if (pre_host_price - normal_host_price) <= -pass_price:
                        temp_support_direction = 1
                    elif (pre_guest_price - normal_guest_price) <= -pass_price:
                        temp_support_direction = -1
                    # 只保存倾向性的support，不保存0
                    if temp_support_direction != 0:
                        handicap_change_support_list.append(temp_support_direction)

            pre_handicap = current_handicap
            pre_host_price = current_host_price
            pre_guest_price = current_guest_price
            count += 1

        # 出现特殊赔率提前结束
        if special_price:
            return False

        # 判断支持方向
        support_direction = 0
        # 完全一致才能表示支持
        if len(handicap_change_support_list)>0 and abs(sum(handicap_change_support_list)) == len(handicap_change_support_list):
            if handicap_change_support_list[0] > 0:
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
        match_algorithm_score = 0
        # 比赛结束才能评分
        if single_match_Item['is_end']:
            if support_direction == 1:
                match_algorithm_score = net_handicap
            elif support_direction == -1:
                match_algorithm_score = -net_handicap

        # # 读取进球数据
        # try:
        #     match_goal_info = self.get_goal_info[single_match_Item['match_id']]
        #     if len(match_goal_info) > 0:
        #         # 目前只记录第一个进球，1表示主队，2表示客队,并且记录时间，如果记录时间《20，则支持该方向的评分为0.2
        #         first_goal_team = match_goal_info[0]['team']
        #         first_goal_time = match_goal_info[0]['time']
        #         if (support_direction == first_goal_team) and first_goal_time <= 20:
        #             match_algorithm_score = 0.2
        #         if support_direction == -1 and first_goal_team == 2 and first_goal_time <= 20:
        #             match_algorithm_score = 0.2
        # except:
        #     print('没有查找到当前比赛的进球数据')
        single_match_Item['macao_handicap'] = ultimate_handicap
        single_match_Item['macao_support_direction'] = support_direction  # 该算法支持方向
        single_match_Item['algorithm_score'] = match_algorithm_score  # 该算法本场比赛评分
        yield single_match_Item