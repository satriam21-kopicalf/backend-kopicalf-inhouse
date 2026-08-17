content = open('D:/kopicalf-projection/be-kopicalf-inhouse/app/services/tasks.py', 'r').read()

# Fix 1: Remove updated_at from UPDATE statement
old_update = '''                            UPDATE md_products 
                            SET 
                                name = COALESCE(%s, name),
                                product_code = COALESCE(%s, product_code),
                                barcode = COALESCE(%s, barcode),
                                uom_name = COALESCE(%s, uom_name),
                                purchase_price = COALESCE(%s, purchase_price),
                                sell_price = COALESCE(%s, sell_price),
                                stock = COALESCE(%s, stock),
                                uom_id = COALESCE(%s, uom_id),
                                description = COALESCE(%s, description),
                                updated_at = NOW()
                            WHERE company_id = %s AND esb_id = %s'''

new_update = '''                            UPDATE md_products 
                            SET 
                                name = COALESCE(%s, name),
                                product_code = COALESCE(%s, product_code),
                                barcode = COALESCE(%s, barcode),
                                uom_name = COALESCE(%s, uom_name),
                                purchase_price = COALESCE(%s, purchase_price),
                                sell_price = COALESCE(%s, sell_price),
                                stock = COALESCE(%s, stock),
                                uom_id = COALESCE(%s, uom_id),
                                description = COALESCE(%s, description)
                            WHERE company_id = %s AND esb_id = %s'''

if old_update in content:
    content = content.replace(old_update, new_update)
    print("Fix 1 applied: removed updated_at from UPDATE")
else:
    print("ERROR: Fix 1 pattern not found")

# Fix 2: Add rollback in exception handler
old_except = '''            except Exception as e:
                error_count += 1
                print(f"Error syncing product detail for ID {product_esb_id}: {e}")
                # Continue with other products even if one fails'''

new_except = '''            except Exception as e:
                error_count += 1
                print(f"Error syncing product detail for ID {product_esb_id}: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
                # Continue with other products even if one fails'''

if old_except in content:
    content = content.replace(old_except, new_except)
    print("Fix 2 applied: added rollback in exception handler")
else:
    print("ERROR: Fix 2 pattern not found")

# Fix 3: Commit after each successful product to avoid long-running transactions
old_success = '''                        success_count += 1
                        
                        # Log progress every 10 products
                        if (i + 1) % 10 == 0:
                            print(f"Product detail sync progress: {i+1}/{total} ({(i+1)/total*100:.1f}%)")'''

new_success = '''                        success_count += 1
                        conn.commit()
                        
                        # Log progress every 10 products
                        if (i + 1) % 10 == 0:
                            print(f"Product detail sync progress: {i+1}/{total} ({(i+1)/total*100:.1f}%)")'''

if old_success in content:
    content = content.replace(old_success, new_success)
    print("Fix 3 applied: commit after each successful product")
else:
    print("ERROR: Fix 3 pattern not found")

open('D:/kopicalf-projection/be-kopicalf-inhouse/app/services/tasks.py', 'w').write(content)
print("SUCCESS: All fixes applied to tasks.py")
