# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html

import pymysql.cursors
import datetime
import logging
import pdb

nowadays = datetime.datetime.now().strftime('%Y_%m_%d')
nowatime = datetime.datetime.now().strftime('%Y_%m_%d_%H%M')

class AokePipeline(object):

    def process_item(self, item, spider):
        if not item:
            return
        # Connect to the database
        config = {
            'host' : 'localhost',
            'user' : 'root',
            'password' : '1994',
            'db' : 'macao_handicap_analysis',
            'charset' : 'utf8mb4',
            'cursorclass' : pymysql.cursors.DictCursor
        }
        connection = pymysql.connect(**config)
        print('连接至数据库macao_handicap_analysis')
        try:
            with connection.cursor() as cursor:
                # 设置当前表名
                tableName = 'aoke_handicap'+nowatime
                # 建表
                build_table = (
                    "CREATE TABLE IF NOT EXISTS "' %s '""
                    "(match_id VARCHAR(16) NOT NULL PRIMARY KEY,"
                    "host VARCHAR(16) NOT NULL,"
                    "guest VARCHAR(16) NOT NULL,"
                    "league_name VARCHAR(16) NOT NULL,"
                    "start_time VARCHAR(20) NOT NULL,"
                    "host_goal INT(2) NOT NULL,"
                    "guest_goal INT(2) NOT NULL,"
                    "is_end BOOLEAN NOT NULL,"
                    "macao_handicap VARCHAR(16) NOT NULL,"
                    "macao_support_direction INT(4) NOT NULL,"
                    "algorithm_score FLOAT(2) NOT NULL)"
                )
                cursor.execute(build_table % tableName)

                cursor.execute('SELECT match_id FROM %s WHERE match_id=%s' % (tableName,item['match_id']))
                table_row_len = len(cursor.fetchall())
                print ('table_row_len:', table_row_len)
                insert_sql = (
                    "INSERT INTO "+tableName+" VALUES "
                    "('%s', '%s', '%s', '%s', '%s', %d, %d, %d, '%s', %d, %f)"
                )
                update_sql = (
                    "UPDATE "+tableName+" SET host_goal="'%s'", guest_goal="'%s'", is_end= %d, macao_support_direction=%d, algorithm_score=%f "
                     "WHERE match_id="+item['match_id']
                )

                try:
                    if table_row_len < 1:
                        print('insert数据库')
                        cursor.execute(insert_sql % (item['match_id'], item['host'], item['guest'], item['league_name'], item['start_time'],item['host_goal'],item['guest_goal'], item['is_end'], item['macao_handicap'], item['macao_support_direction'], item['algorithm_score']))
                    else:
                        print('update数据库')
                        cursor.execute(update_sql %
                       (item['host_goal'], item['guest_goal'], item['is_end'], item['macao_support_direction'], item['algorithm_score'])
                        )
                except Exception as e:
                    print("数据库执行失败 ",e)
            # connection is not autocommit by default. So you must commit to save your changes.
            cursor.close()
            if not connection.commit():
                connection.rollback()
        finally:
            connection.close()

        return item
