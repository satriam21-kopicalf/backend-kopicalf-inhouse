import os

file_path = "d:/kopicalf-projection/be-kopicalf-inhouse/app/services/tasks.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. product_values
old1 = """                    if entity == "PRODUCT":
                        product_values.append((
                            esb_id, company_id, parsed_item.productName, parsed_item.productCode, parsed_item.bomName, 
                            parsed_item.categoryName, parsed_item.subCategoryName, parsed_item.categoryTypeName, 
                            parsed_item.flagActive if parsed_item.flagActive is not None else 1, parsed_item.barcode, parsed_item.uomName, 
                            parsed_item.purchasePrice, parsed_item.sellPrice, parsed_item.stock, 
                            bool(parsed_item.hasVariant) if parsed_item.hasVariant is not None else False, 
                            bool(parsed_item.isRawMaterial) if parsed_item.isRawMaterial is not None else False, 
                            bool(parsed_item.isProduction) if parsed_item.isProduction is not None else False, 
                            parsed_item.imageUrl
                        ))"""
new1 = """                    if entity == "PRODUCT":
                        product_values.append((
                            esb_id, company_id, parsed_item.productName, parsed_item.productCode, parsed_item.bomName, 
                            parsed_item.categoryName, parsed_item.subCategoryName, parsed_item.categoryTypeName, 
                            parsed_item.flagActive if parsed_item.flagActive is not None else 1, parsed_item.barcode, parsed_item.uomName, 
                            parsed_item.purchasePrice, parsed_item.sellPrice, parsed_item.stock, 
                            bool(parsed_item.hasVariant) if parsed_item.hasVariant is not None else False, 
                            bool(parsed_item.isRawMaterial) if parsed_item.isRawMaterial is not None else False, 
                            bool(parsed_item.isProduction) if parsed_item.isProduction is not None else False, 
                            parsed_item.imageUrl, parsed_item.productAlias, parsed_item.categoryID, parsed_item.subCategoryID,
                            parsed_item.uomID, parsed_item.bomID, parsed_item.pricelistID, parsed_item.minStock, parsed_item.maxStock,
                            parsed_item.isTrackInventory, parsed_item.description
                        ))"""
content = content.replace(old1, new1)

# 2. sub_category_values
old2 = """                    elif entity == "PRODUCT_SUB_CATEGORY":
                        sub_category_values.append((
                            esb_id, company_id, parsed_item.categoryID, parsed_item.subCategoryCode,
                            parsed_item.subCategoryName, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))"""
new2 = """                    elif entity == "PRODUCT_SUB_CATEGORY":
                        sub_category_values.append((
                            esb_id, company_id, parsed_item.categoryID, parsed_item.subCategoryCode,
                            parsed_item.subCategoryName, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True,
                            parsed_item.displayOrder
                        ))"""
content = content.replace(old2, new2)

# 3. branch_product_values
old3 = """                    elif entity == "BRANCH_PRODUCT":
                        branch_product_values.append((
                            esb_id, company_id, parsed_item.branchID, parsed_item.productID,
                            parsed_item.stock, parsed_item.availableStock, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))"""
new3 = """                    elif entity == "BRANCH_PRODUCT":
                        branch_product_values.append((
                            esb_id, company_id, parsed_item.branchID, parsed_item.productID,
                            parsed_item.stock, parsed_item.availableStock, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True,
                            parsed_item.productCode, parsed_item.productName, parsed_item.branchName, parsed_item.locationID,
                            parsed_item.locationName, parsed_item.minStock, parsed_item.maxStock, parsed_item.reservedStock
                        ))"""
content = content.replace(old3, new3)

# 4. pricelist_values
old4 = """                    elif entity == "PRICELIST":
                        pricelist_values.append((
                            esb_id, company_id, parsed_item.productID, parsed_item.branchID,
                            parsed_item.price, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True
                        ))"""
new4 = """                    elif entity == "PRICELIST":
                        pricelist_values.append((
                            esb_id, company_id, parsed_item.productID, parsed_item.branchID,
                            parsed_item.price, bool(parsed_item.flagActive) if parsed_item.flagActive is not None else True,
                            parsed_item.priceDate, parsed_item.supplierName, parsed_item.productName, parsed_item.productCode,
                            parsed_item.unitName, parsed_item.currency, parsed_item.expiredDate
                        ))"""
content = content.replace(old4, new4)

# 5. md_products INSERT
old5 = """                    INSERT INTO md_products (
                        esb_id, company_id, name, product_code, bom_name, category_name, sub_category_name, category_type_name, 
                        flag_active, barcode, uom_name, purchase_price, sell_price, stock, has_variant, 
                        is_raw_material, is_production, image_url
                    )
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, product_code = EXCLUDED.product_code, bom_name = EXCLUDED.bom_name,
                        category_name = EXCLUDED.category_name, sub_category_name = EXCLUDED.sub_category_name,
                        category_type_name = EXCLUDED.category_type_name, flag_active = EXCLUDED.flag_active,
                        barcode = EXCLUDED.barcode, uom_name = EXCLUDED.uom_name, purchase_price = EXCLUDED.purchase_price,
                        sell_price = EXCLUDED.sell_price, stock = EXCLUDED.stock, has_variant = EXCLUDED.has_variant,
                        is_raw_material = EXCLUDED.is_raw_material, is_production = EXCLUDED.is_production, image_url = EXCLUDED.image_url"""
new5 = """                    INSERT INTO md_products (
                        esb_id, company_id, name, product_code, bom_name, category_name, sub_category_name, category_type_name, 
                        flag_active, barcode, uom_name, purchase_price, sell_price, stock, has_variant, 
                        is_raw_material, is_production, image_url, product_alias, category_id, sub_category_id,
                        uom_id, bom_id, pricelist_id, min_stock, max_stock, is_track_inventory, description
                    )
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, product_code = EXCLUDED.product_code, bom_name = EXCLUDED.bom_name,
                        category_name = EXCLUDED.category_name, sub_category_name = EXCLUDED.sub_category_name,
                        category_type_name = EXCLUDED.category_type_name, flag_active = EXCLUDED.flag_active,
                        barcode = EXCLUDED.barcode, uom_name = EXCLUDED.uom_name, purchase_price = EXCLUDED.purchase_price,
                        sell_price = EXCLUDED.sell_price, stock = EXCLUDED.stock, has_variant = EXCLUDED.has_variant,
                        is_raw_material = EXCLUDED.is_raw_material, is_production = EXCLUDED.is_production, image_url = EXCLUDED.image_url,
                        product_alias = EXCLUDED.product_alias, category_id = EXCLUDED.category_id, sub_category_id = EXCLUDED.sub_category_id,
                        uom_id = EXCLUDED.uom_id, bom_id = EXCLUDED.bom_id, pricelist_id = EXCLUDED.pricelist_id, min_stock = EXCLUDED.min_stock,
                        max_stock = EXCLUDED.max_stock, is_track_inventory = EXCLUDED.is_track_inventory, description = EXCLUDED.description"""
content = content.replace(old5, new5)

# 6. md_sub_categories INSERT
old6 = """                    INSERT INTO md_sub_categories (esb_id, company_id, category_esb_id, code, name, flag_active)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        category_esb_id = EXCLUDED.category_esb_id, code = EXCLUDED.code, name = EXCLUDED.name, flag_active = EXCLUDED.flag_active"""
new6 = """                    INSERT INTO md_sub_categories (esb_id, company_id, category_esb_id, code, name, flag_active, display_order)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        category_esb_id = EXCLUDED.category_esb_id, code = EXCLUDED.code, name = EXCLUDED.name, flag_active = EXCLUDED.flag_active,
                        display_order = EXCLUDED.display_order"""
content = content.replace(old6, new6)

# 7. md_branch_products INSERT
old7 = """                    INSERT INTO md_branch_products (esb_id, company_id, branch_esb_id, product_esb_id, stock, available_stock, flag_active)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        branch_esb_id = EXCLUDED.branch_esb_id, product_esb_id = EXCLUDED.product_esb_id,
                        stock = EXCLUDED.stock, available_stock = EXCLUDED.available_stock, flag_active = EXCLUDED.flag_active"""
new7 = """                    INSERT INTO md_branch_products (esb_id, company_id, branch_esb_id, product_esb_id, stock, available_stock, flag_active,
                        product_code, product_name, branch_name, location_id, location_name, min_stock, max_stock, reserved_stock)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        branch_esb_id = EXCLUDED.branch_esb_id, product_esb_id = EXCLUDED.product_esb_id,
                        stock = EXCLUDED.stock, available_stock = EXCLUDED.available_stock, flag_active = EXCLUDED.flag_active,
                        product_code = EXCLUDED.product_code, product_name = EXCLUDED.product_name, branch_name = EXCLUDED.branch_name,
                        location_id = EXCLUDED.location_id, location_name = EXCLUDED.location_name, min_stock = EXCLUDED.min_stock,
                        max_stock = EXCLUDED.max_stock, reserved_stock = EXCLUDED.reserved_stock"""
content = content.replace(old7, new7)

# 8. md_pricelists INSERT
old8 = """                    INSERT INTO md_pricelists (esb_id, company_id, product_esb_id, branch_esb_id, price, flag_active)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        product_esb_id = EXCLUDED.product_esb_id, branch_esb_id = EXCLUDED.branch_esb_id,
                        price = EXCLUDED.price, flag_active = EXCLUDED.flag_active"""
new8 = """                    INSERT INTO md_pricelists (esb_id, company_id, product_esb_id, branch_esb_id, price, flag_active,
                        price_date, supplier_name, product_name, product_code, unit_name, currency, expired_date)
                    VALUES %s
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        product_esb_id = EXCLUDED.product_esb_id, branch_esb_id = EXCLUDED.branch_esb_id,
                        price = EXCLUDED.price, flag_active = EXCLUDED.flag_active,
                        price_date = NULLIF(EXCLUDED.price_date, ''), supplier_name = EXCLUDED.supplier_name, product_name = EXCLUDED.product_name,
                        product_code = EXCLUDED.product_code, unit_name = EXCLUDED.unit_name, currency = EXCLUDED.currency, expired_date = NULLIF(EXCLUDED.expired_date, '')"""
content = content.replace(old8, new8)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("tasks.py updated successfully.")
