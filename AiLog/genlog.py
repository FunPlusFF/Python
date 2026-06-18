# generate_test_log.py - Генератор тестовых логов Greenplum
import random
from datetime import datetime, timedelta
from pathlib import Path

def generate_greenplum_log(output_file="test_greenplum_log.csv", num_entries=100):
    """
    Генерирует реалистичный лог Greenplum в формате CSV
    Формат: 28 колонок, разделенных запятыми
    """
    
    # Данные для генерации
    users = ['gpadmin', 'etl_user', 'analyst', 'app_user', 'report_user', 'dba']
    databases = ['warehouse', 'analytics', 'reporting', 'staging', 'prod_db', 'etl_db']
    hosts = ['192.168.1.10', '192.168.1.20', '192.168.1.30', '10.0.0.5', '10.0.0.6', 'mdw']
    segments = ['seg0', 'seg1', 'seg2', 'seg3', 'seg4', 'seg-1', 'seg5']
    ports = ['5432', '5432', '5432', '40000', '40001']
    
    # Шаблоны ошибок с разными severity
    error_scenarios = [
        # 1. OUT OF MEMORY ошибки (ERROR/FATAL)
        {
            'weight': 15,
            'severity': random.choices(['ERROR', 'FATAL'], weights=[70, 30])[0],
            'sql_states': ['53200', '53000', '53300'],
            'messages': [
                'out of memory',
                'segment process failed out of memory (work_mem exceeded)',
                'gp_vmem_protect_limit exceeded for query',
                'out of memory - failed to allocate 256MB',
                'Virtual Memory exhausted on segment',
                'Memory exhausted during hash join operation',
            ],
            'details': [
                'Failed on segment seg2',
                'Memory used: 2048MB, limit: 2048MB',
                'vm_overcommit_ratio=95',
                'Requested: 512MB, Available: 128MB',
                'work_mem setting: 64MB',
            ],
            'hints': [
                'Increase gp_vmem_protect_limit or reduce work_mem',
                'Consider partitioning the query',
                'Reduce concurrent queries',
            ],
            'queries': [
                'SELECT * FROM large_fact f JOIN dim_customer c ON f.cust_id = c.id WHERE date >= ''2024-01-01''',
                'CREATE TABLE temp_agg AS SELECT dept_id, SUM(amount) FROM transactions GROUP BY dept_id',
                'UPDATE large_table SET status = ''processed'' WHERE date = ''2026-06-18''',
                'INSERT INTO summary SELECT * FROM staging.large_export',
            ],
            'type': 'OUT_OF_MEMORY'
        },
        
        # 2. QUERY SYNTAX ошибки
        {
            'weight': 20,
            'severity': 'ERROR',
            'sql_states': ['42P01', '42703', '42883', '42601'],
            'messages': [
                'relation "sales_fact" does not exist',
                'relation "customer_dim" does not exist',
                'missing FROM-clause entry for table "staging"',
                'syntax error at or near "SELECT"',
                'column "nonexistent_column" does not exist',
                'function "unknown_func" does not exist',
                'relation "temp_analysis" does not exist',
                'schema "reporting" does not exist',
            ],
            'details': [
                '',
                'Error occurred during query planning',
                'LINE 1: SELECT * FROM ',
                'Perhaps you meant to reference the column "amount"',
            ],
            'hints': [
                '',
                'Check table name spelling',
                'Verify schema search path',
            ],
            'queries': [
                'SELECT * FROM sales_fact WHERE date >= ''2026-01-01''',
                'INSERT INTO sales_fact SELECT * FROM staging.sales_data',
                'SELECT * FROM staging.sales_data',
                'SELECT dept_id, SUM(amount FROM transactions',
                'SELECT nonexistent_column FROM orders',
            ],
            'type': 'QUERY_ERROR'
        },
        
        # 3. DUPLICATE KEY ошибки
        {
            'weight': 15,
            'severity': 'ERROR',
            'sql_states': ['23505'],
            'messages': [
                'duplicate key value violates unique constraint "pk_orders"',
                'duplicate key value violates unique constraint "pk_customers"',
                'duplicate key value violates unique constraint "pk_transactions"',
                'duplicate key value violates unique constraint "idx_unique_invoice"',
            ],
            'details': [
                'Key (order_id)=(12345) already exists.',
                'Key (customer_id)=(67890) already exists.',
                'Key (transaction_id)=(UUID-1234-5678) already exists.',
            ],
            'hints': [
                '',
                'Use ON CONFLICT clause to handle duplicates',
                'Check for duplicate entries in source data',
            ],
            'queries': [
                'INSERT INTO orders VALUES (12345, ''product_A'', 100)',
                'INSERT INTO customers (id, name) VALUES (67890, ''John Doe'')',
                'COPY orders FROM ''/data/new_orders.csv'' CSV',
            ],
            'type': 'DUPLICATE_KEY'
        },
        
        # 4. DATA FORMAT ошибки (WARNING)
        {
            'weight': 10,
            'severity': 'WARNING',
            'sql_states': ['01000', '22000', '22P02'],
            'messages': [
                'skipping external table row due to data format error',
                'invalid input syntax for type integer: "abc"',
                'invalid input syntax for type timestamp: "not_a_date"',
                'value too long for type varchar(50)',
                'numeric field overflow',
            ],
            'details': [
                'Row: 1523, Column: amount',
                'Bad value: "N/A" for numeric column',
                'External table: ext_sales',
            ],
            'hints': [
                '',
                'Check external table definition',
                'Use error logging table to capture bad rows',
            ],
            'queries': [
                'SELECT * FROM ext_external_table',
                'INSERT INTO facts SELECT * FROM external_source',
                'COPY sales FROM ''/data/sales.csv'' WITH CSV',
            ],
            'type': 'DATA_ERROR'
        },
        
        # 5. PANIC / SEGMENT FAILURE
        {
            'weight': 5,
            'severity': 'PANIC',
            'sql_states': ['XX000', '58000', '57P03'],
            'messages': [
                'Unexpected internal error',
                'segment process failed',
                'received signal SIGSEGV',
                'shared memory corruption detected',
                'checkpoint failure on segment',
            ],
            'details': [
                'Segment: seg3 on host 10.0.0.5',
                'Process: slice1 executor',
                'Stack trace available in pg_log',
            ],
            'hints': [
                'Restart segment with gprecoverseg',
                'Check hardware (memory, disk) on affected host',
                'Contact support',
            ],
            'queries': [
                '',
                'SELECT * FROM very_large_table WHERE complex_condition()',
            ],
            'type': 'PANIC'
        },
        
        # 6. INTERCONNECT / NETWORK ошибки
        {
            'weight': 10,
            'severity': 'ERROR',
            'sql_states': ['58000', '08006', '57P03'],
            'messages': [
                'interconnect error: Connection refused',
                'failed to connect to segment on host 10.0.0.5',
                'interconnect timeout after 180s',
                'broken pipe on interconnect',
                'interconnect error: Connection reset by peer',
            ],
            'details': [
                'Source: seg0, Target: seg5',
                'Network interface: eth0',
                'Retry count: 3, all failed',
            ],
            'hints': [
                'Check network connectivity between hosts',
                'Verify firewall rules',
                'Check gp_interconnect_type parameter',
            ],
            'queries': [
                'SELECT /*+ broadcast(t2) */ * FROM large_fact t1 JOIN large_dim t2 ON t1.id = t2.id',
            ],
            'type': 'INTERCONNECT_ERROR'
        },
        
        # 7. DEADLOCK ошибки
        {
            'weight': 8,
            'severity': 'ERROR',
            'sql_states': ['40P01'],
            'messages': [
                'deadlock detected',
                'deadlock detected while waiting for ShareLock',
                'process 12345 detected deadlock',
            ],
            'details': [
                'Process 12345 waits for ShareLock on transaction 67890; blocked by process 11111',
                'Process 11111 waits for ShareLock on transaction 12345; blocked by process 12345',
            ],
            'hints': [
                'Retry the transaction',
                'Review application transaction logic',
            ],
            'queries': [
                'UPDATE orders SET status = ''shipped'' WHERE id IN (SELECT order_id FROM order_items WHERE qty > 100)',
                'DELETE FROM temp_lock_test WHERE id = 555',
            ],
            'type': 'DEADLOCK'
        },
        
        # 8. DISK ошибки
        {
            'weight': 5,
            'severity': random.choices(['ERROR', 'FATAL'], weights=[60, 40])[0],
            'sql_states': ['53100', '53200'],
            'messages': [
                'could not write to file "base/16384/12345": No space left on device',
                'disk full on segment seg4',
                'I/O error on segment seg1',
                'could not read block 12345 in relation "large_table": Input/output error',
            ],
            'details': [
                'Filesystem: /data/primary/gpseg4',
                'Available space: 0 bytes',
            ],
            'hints': [
                'Free up disk space on affected segment',
                'Check filesystem health',
            ],
            'queries': [
                'INSERT INTO large_table SELECT * FROM staging.backup_data',
            ],
            'type': 'DISK_ERROR'
        },
        
        # 9. CONNECTION ошибки
        {
            'weight': 7,
            'severity': 'ERROR',
            'sql_states': ['08000', '08003', '08006', '53300'],
            'messages': [
                'too many clients already',
                'authentication failed for user "app_user"',
                'connection limit exceeded for database "warehouse"',
                'connection refused',
            ],
            'details': [
                'Max connections: 500, Current: 500',
                '',
            ],
            'hints': [
                'Increase max_connections in postgresql.conf',
                'Close idle connections',
            ],
            'queries': [
                '',
            ],
            'type': 'CONNECTION_ERROR'
        },
        
        # 10. INFO / LOG записи (не ошибки, для реалистичности)
        {
            'weight': 5,
            'severity': 'LOG',
            'sql_states': ['00000'],
            'messages': [
                'checkpoint starting: time',
                'checkpoint complete: wrote 1234 buffers',
                'autovacuum: processing database "warehouse"',
                'statement: SELECT COUNT(*) FROM orders',
            ],
            'details': ['', ''],
            'hints': [''],
            'queries': [
                'SELECT COUNT(*) FROM orders WHERE date > ''2026-01-01''',
                'VACUUM ANALYZE sales_fact',
            ],
            'type': 'INFO'
        },
    ]
    
    # Время начала лога
    base_time = datetime(2026, 6, 18, 14, 0, 0)
    
    entries = []
    
    # Генерируем записи
    for i in range(num_entries):
        # Выбираем сценарий с учетом весов
        weights = [s['weight'] for s in error_scenarios]
        scenario = random.choices(error_scenarios, weights=weights, k=1)[0]
        
        # Генерируем время (с нарастающей плотностью ошибок)
        if random.random() < 0.7:  # 70% ошибок ближе к концу периода
            time_offset = timedelta(
                seconds=random.randint(1800, 3600)  # Последние 30 минут
            )
        else:
            time_offset = timedelta(
                seconds=random.randint(0, 3600)  # Весь час
            )
        
        event_time = base_time + time_offset
        
        # Формат времени: "2026-06-18 142345.123 UTC"
        timestamp = event_time.strftime('%Y-%m-%d %H%M%S.') + f"{random.randint(0, 999):03d} UTC"
        session_start = (event_time - timedelta(seconds=random.randint(1, 600))).strftime('%Y-%m-%d %H%M%S UTC')
        
        # Генерируем поля
        user = random.choice(users)
        database = random.choice(databases)
        pid = f"p{random.randint(10000, 99999)}"
        thread_id = f"th-{random.randint(100000000, 999999999)}"
        remote_host = random.choice(hosts)
        remote_port = random.choice(ports)
        transaction_id = str(random.randint(0, 9999))
        session_id = f"con{random.randint(1000, 9999)}"
        command_id = f"cmd{random.randint(1, 200)}"
        segment = random.choice(segments)
        slice_id = f"slice-{random.randint(0, 10)}"
        
        severity = scenario['severity']
        sql_state = random.choice(scenario['sql_states'])
        message = random.choice(scenario['messages'])
        detail = random.choice(scenario['details']) if scenario['details'] else ''
        hint = random.choice(scenario['hints']) if scenario['hints'] else ''
        query = random.choice(scenario['queries']) if scenario['queries'] else ''
        
        # Собираем строку CSV
        # Формат: event_time,user,database,pid,thread,host,port,session_start,tx_id,session,cmd,segment,slice,severity,sql_state,message,detail,hint,internal_q,internal_q_pos,context,debug_q,cursor_pos,func,file,line,stack
        row = [
            timestamp,                    # event_time
            user,                         # user_name
            database,                     # database_name
            pid,                          # process_id
            thread_id,                    # thread_id
            remote_host,                  # remote_host
            remote_port,                  # remote_port
            session_start,                # session_start_time
            transaction_id,              # transaction_id
            session_id,                   # session_id
            command_id,                   # command_id
            segment,                      # segment_id
            slice_id,                     # slice_id
            severity,                     # severity
            sql_state,                    # sql_state_code
            message,                      # message
            detail,                       # detail
            hint,                         # hint
            '',                           # internal_query
            '',                           # internal_query_pos
            '',                           # context
            query,                        # debug_query_string
            '0',                          # error_cursor_pos
            '',                           # func_name
            '',                           # file_name
            '',                           # file_line
            '',                           # stack_trace
        ]
        
        entries.append(','.join(row))
    
    # Сортируем по времени
    entries.sort()
    
    # Записываем в файл
    with open(output_file, 'w', encoding='utf-8') as f:
        # Заголовок (как в реальных логах GP)
        f.write('event_time,user_name,database_name,process_id,thread_id,remote_host,remote_port,session_start_time,transaction_id,session_id,command_id,segment_id,slice_id,severity,sql_state_code,message,detail,hint,internal_query,internal_query_pos,context,debug_query_string,error_cursor_pos,func_name,file_name,file_line,stack_trace\n')
        
        for entry in entries:
            f.write(entry + '\n')
    
    # Статистика
    severity_count = {}
    for entry in entries:
        sev = entry.split(',')[13]
        severity_count[sev] = severity_count.get(sev, 0) + 1
    
    print(f"Generated {len(entries)} log entries in: {output_file}")
    print(f"\nStatistics:")
    for sev, count in sorted(severity_count.items()):
        print(f"  {sev}: {count} entries")
    
    return output_file


def generate_small_test_file(output_file="quick_test.csv"):
    """Генерирует маленький файл для быстрой проверки парсера"""
    
    sample_entries = [
        # ERROR - OUT_OF_MEMORY
        "2026-06-18 142345.124 UTC,gpadmin,warehouse,p12345,th-987654321,192.168.1.10,5432,2026-06-18 142340 UTC,0,con1234,cmd45,seg2,slice-1,ERROR,53200,out of memory,work_mem exceeded on seg2,Increase gp_vmem_protect_limit,,0,,INSERT INTO sales_fact SELECT * FROM staging.data,0,,,",
        
        # ERROR - QUERY SYNTAX
        "2026-06-18 142412.456 UTC,gpadmin,etl_db,p54321,th-123456789,10.0.0.5,5432,2026-06-18 142400 UTC,0,con5678,cmd89,seg-1,slice-0,ERROR,42P01,relation \"sales_fact\" does not exist,,,,0,,SELECT * FROM sales_fact WHERE date='2026-06-18',0,,,",
        
        # ERROR - DUPLICATE KEY
        "2026-06-18 142833.789 UTC,gpadmin,analytics,p67890,th-555555555,192.168.1.20,5432,2026-06-18 142800 UTC,0,con9999,cmd101,seg4,slice-3,ERROR,23505,duplicate key value violates unique constraint pk_orders,Key (order_id)=(12345) already exists.,Use ON CONFLICT clause,,0,,INSERT INTO orders VALUES (12345,'product_A',100),0,,,",
        
        # WARNING - DATA FORMAT
        "2026-06-18 143001.000 UTC,gpadmin,warehouse,p11111,th-999999999,10.0.0.6,5432,2026-06-18 142955 UTC,0,con2222,cmd55,seg-1,slice-1,WARNING,01000,skipping external table row due to data format error,invalid input syntax for type integer: \"abc\",Check external table definition,,0,,SELECT * FROM ext_external_table,0,,,",
        
        # FATAL - SEGMENT FAILURE
        "2026-06-18 143145.333 UTC,gpadmin,prod_db,p33333,th-111111111,192.168.1.30,5432,2026-06-18 143100 UTC,0,con4444,cmd77,seg3,slice-5,FATAL,57P03,segment process failed out of memory (work_mem exceeded),Memory used: 2048MB limit: 2048MB,Reduce work_mem or increase gp_vmem_protect_limit,,0,,UPDATE large_table SET status='processed' WHERE date='2026-06-18',0,,,",
        
        # PANIC - INTERNAL ERROR
        "2026-06-18 143256.789 UTC,gpadmin,prod_db,p55555,th-222222222,10.0.0.5,5432,2026-06-18 143200 UTC,0,con6666,cmd112,seg1,slice-2,PANIC,XX000,Unexpected internal error,received signal SIGSEGV on seg1,Restart segment with gprecoverseg,,0,,SELECT * FROM very_large_table WHERE complex_condition(),0,,,",
        
        # ERROR - INTERCONNECT
        "2026-06-18 143422.111 UTC,gpadmin,analytics,p77777,th-333333333,192.168.1.10,5432,2026-06-18 143400 UTC,0,con8888,cmd134,seg0,slice-4,ERROR,58000,interconnect error: Connection refused,Failed to connect to seg5 on host 10.0.0.5,Check network connectivity,,0,,SELECT /*+ broadcast(t2) */ * FROM large_fact t1 JOIN large_dim t2 ON t1.id=t2.id,0,,,",
        
        # ERROR - DEADLOCK
        "2026-06-18 143533.456 UTC,gpadmin,reporting,p99999,th-444444444,10.0.0.6,5432,2026-06-18 143500 UTC,0,con1111,cmd156,seg2,slice-1,ERROR,40P01,deadlock detected,Process 12345 waits for ShareLock on transaction 67890 blocked by process 11111,Retry the transaction,,0,,UPDATE orders SET status='shipped' WHERE id IN (SELECT order_id FROM order_items WHERE qty>100),0,,,",
        
        # ERROR - DISK
        "2026-06-18 143644.789 UTC,gpadmin,warehouse,p22222,th-555555555,192.168.1.20,5432,2026-06-18 143600 UTC,0,con3333,cmd178,seg4,slice-0,ERROR,53100,could not write to file base/16384/12345: No space left on device,Filesystem /data/primary/gpseg4 full,Free up disk space,,0,,INSERT INTO large_table SELECT * FROM staging.backup,0,,,",
        
        # ERROR - CONNECTION
        "2026-06-18 143755.222 UTC,gpadmin,prod_db,p44444,th-666666666,192.168.1.30,5432,2026-06-18 143700 UTC,0,con5555,cmd189,seg-1,slice-0,ERROR,53300,too many clients already,Max connections: 500 Current: 500,Increase max_connections or close idle connections,,0,,,0,,,",
    ]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('event_time,user_name,database_name,process_id,thread_id,remote_host,remote_port,session_start_time,transaction_id,session_id,command_id,segment_id,slice_id,severity,sql_state_code,message,detail,hint,internal_query,internal_query_pos,context,debug_query_string,error_cursor_pos,func_name,file_name,file_line,stack_trace\n')
        for entry in sample_entries:
            f.write(entry + '\n')
    
    print(f"Generated {len(sample_entries)} test entries in: {output_file}")
    return output_file


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'small':
        # Генерируем маленький тестовый файл
        generate_small_test_file()
    else:
        # Генерируем большой реалистичный файл
        generate_greenplum_log("test_greenplum_log.csv", num_entries=100)
    
    print("\nDone! File is ready for parser testing.")