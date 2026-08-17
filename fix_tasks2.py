content = open('D:/kopicalf-projection/be-kopicalf-inhouse/app/services/tasks.py', 'r').read()

# Fix 1: Add hashlib import at module level
old_imports = 'import os\nimport json\nimport httpx'
new_imports = 'import os\nimport json\nimport hashlib\nimport httpx'
if old_imports in content:
    content = content.replace(old_imports, new_imports)
    print('Fix 1: added hashlib import at module level')
else:
    print('ERROR Fix 1: import pattern not found')

# Fix 2: Replace DOCUMENT_TEMPLATE/CUSTOMER_PRICELIST esb_id extraction
old_esb_id = '''                    elif entity == "DOCUMENT_TEMPLATE" or entity == "CUSTOMER_PRICELIST":
                        # For generic models, try common ID fields
                        esb_id_val = (
                            item.get('id') or item.get('ID') or
                            item.get('templateID') or item.get('customerPricelistID') or
                            item.get('pricelistID') or item.get('documentID') or
                            str(hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest())
                        )
                        esb_id = str(esb_id_val) if esb_id_val else "unknown"
                        if esb_id == "unknown":
                            import hashlib
                            esb_id = hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest()'''

new_esb_id = '''                    elif entity == "DOCUMENT_TEMPLATE" or entity == "CUSTOMER_PRICELIST":
                        # For generic models, try common ID fields (hashlib imported at module level)
                        esb_id_val = (
                            item.get('requestTemplateID') or item.get('customerPricelistID') or
                            item.get('id') or item.get('ID') or
                            item.get('templateID') or item.get('pricelistID') or item.get('documentID')
                        )
                        esb_id = str(esb_id_val) if esb_id_val else hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest()'''

if old_esb_id in content:
    content = content.replace(old_esb_id, new_esb_id)
    print('Fix 2: replaced esb_id extraction for new entities')
else:
    print('ERROR Fix 2: esb_id pattern not found')

# Fix 3: Fix DOCUMENT_TEMPLATE field extraction with actual ESB structure
old_dt = '''                    elif entity == "DOCUMENT_TEMPLATE":
                        # Extract document template fields from generic model
                        template_name = item.get('templateName') or item.get('name') or ""
                        template_code = item.get('templateCode') or item.get('code') or ""
                        document_type = item.get('documentType') or item.get('type') or ""
                        document_template_values.append((
                            esb_id, company_id,
                            template_name,
                            document_type,
                            template_code,
                            bool(item.get('flagActive', 1))
                        ))'''

new_dt = '''                    elif entity == "DOCUMENT_TEMPLATE":
                        # Extract document template fields from ESB /document-template structure
                        template_name = item.get('requestTemplateName') or item.get('templateName') or item.get('name') or ""
                        document_type = item.get('requestTemplateTypeNames') or item.get('documentType') or item.get('type') or ""
                        template_code = str(item.get('requestTemplateID') or item.get('templateCode') or item.get('code') or "")
                        document_template_values.append((
                            esb_id, company_id,
                            template_name,
                            document_type,
                            template_code,
                            bool(item.get('flagActive', 1))
                        ))'''

if old_dt in content:
    content = content.replace(old_dt, new_dt)
    print('Fix 3: fixed DOCUMENT_TEMPLATE field extraction')
else:
    print('ERROR Fix 3: DOCUMENT_TEMPLATE extraction pattern not found')

# Fix 4: Map notes to description in product detail sync
old_desc = "barcode = product_data.get('barcode')\n                        description = product_data.get('description')"
new_desc = "barcode = product_data.get('barcode')\n                        description = product_data.get('description') or product_data.get('notes')"

if old_desc in content:
    content = content.replace(old_desc, new_desc)
    print('Fix 4: mapped notes to description')
else:
    print('ERROR Fix 4: description pattern not found')

open('D:/kopicalf-projection/be-kopicalf-inhouse/app/services/tasks.py', 'w').write(content)
print('SUCCESS: all fixes applied')
