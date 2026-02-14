# 02_CSVスキーマ

CSVはUTF-8、カンマ区切り、先頭行はヘッダ。
日時は ISO8601（例: 2026-02-12T09:15:00+09:00）

## generation_run.csv
run_id,generated_at,start_date,end_date,seed,generator_version

## visit.csv
visit_id,store_id,table_id,seated_at,left_at,adult_cnt,child_cnt,visit_date,day_of_week,time_slot

## order.csv
order_id,visit_id,ordered_at,channel,order_seq_in_visit

## order_item.csv
order_item_id,order_id,menu_item_id,qty,unit_price_yen_at_order,line_subtotal_yen,status,served_at,cook_time_sec,is_kids_item

## receipt.csv
receipt_id,visit_id,paid_at,payment_method,customer_id,subtotal_yen,discount_total_yen,tax_rate_applied,tax_rate_hist_id,tax_yen,total_yen,applied_discount_ids,points_earned,points_used

## change_log.csv
change_id,entity_type,entity_id,change_type,changed_at,effective_from,effective_to,summary

## menu_item.csv
menu_item_id,name,category,is_kids_item,season,event

## menu_price_history.csv
menu_price_hist_id,menu_item_id,price_yen,effective_from,effective_to

## set_discount.csv
discount_id,name,discount_type,discount_value_yen,discount_rate,effective_from,effective_to

## tax_rate_history.csv
tax_rate_hist_id,effective_from,effective_to,tax_rate,tax_rule

## customer.csv
customer_id,created_at
