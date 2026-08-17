content = open('D:/kopicalf-projection/be-kopicalf-inhouse/app/services/tasks.py', 'r').read()

old_status_section = '''        status = "FAILED" if has_error else "SUCCESS"
        cur.execute('''
new_status_section = '''        # After successful PRODUCT sync, trigger product detail sync
        if entity == "PRODUCT" and not has_error:
            print(f"Starting product detail sync for company {company_id}...")
            detail_sync_result = sync_product_details(company_id, client, conn, cur)
            print(f"Product detail sync completed: {detail_sync_result['error_msg']}")
            
            # Update sync history with detail sync info
            if detail_sync_result["errors"] > 0:
                has_error = True
                error_msg = f"PRODUCT sync OK but detail sync had {detail_sync_result['errors']} errors: {detail_sync_result['error_msg']}"

        status = "FAILED" if has_error else "SUCCESS"
        cur.execute('''

if old_status_section in content:
    content = content.replace(old_status_section, new_status_section)
    print("Added product detail sync trigger")
else:
    print("Pattern not found for status section")

open('D:/kopicalf-projection/be-kopicalf-inhouse/app/services/tasks.py', 'w').write(content)
print("SUCCESS: Added product detail sync trigger")
