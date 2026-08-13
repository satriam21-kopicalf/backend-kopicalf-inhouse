import os

file_path = "d:/kopicalf-projection/fe-kopicalf-inhouse/src/components/LiveDataTable.tsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Product
old1 = """      case 'product':
        return [
          { key: 'index', label: '#' },
          { key: 'productName', label: 'Product Name' },
          { key: 'productCode', label: 'Product Code' },
          { key: 'bomName', label: 'Bom Name' },
          { key: 'categoryName', label: 'Category' },
          { key: 'subCategoryName', label: 'Sub Category' },
          { key: 'categoryTypeName', label: 'Category Type' },
          { key: 'status', label: 'Status' }
        ];"""
new1 = """      case 'product':
        return [
          { key: 'index', label: '#' },
          { key: 'productName', label: 'Product Name' },
          { key: 'productCode', label: 'Product Code' },
          { key: 'uomName', label: 'UOM' },
          { key: 'sellPrice', label: 'Sell Price' },
          { key: 'stock', label: 'Stock' },
          { key: 'bomName', label: 'BOM Name' },
          { key: 'categoryName', label: 'Category' },
          { key: 'subCategoryName', label: 'Sub Category' },
          { key: 'status', label: 'Status' }
        ];"""
content = content.replace(old1, new1)

# 2. Sub Category
old2 = """      case 'sub-category':
        return [
          { key: 'subCategoryName', label: 'Sub Category Name' },
          { key: 'notes', label: 'Notes' },
          { key: 'deadStockThreshold', label: 'Dead Stock Threshold (Days)' },
          { key: 'status', label: 'Status' },
          { key: 'actions:edit,delete', label: 'Action' }
        ];"""
new2 = """      case 'sub-category':
        return [
          { key: 'subCategoryName', label: 'Sub Category Name' },
          { key: 'categoryName', label: 'Parent Category' },
          { key: 'notes', label: 'Notes' },
          { key: 'deadStockThreshold', label: 'Dead Stock Threshold (Days)' },
          { key: 'status', label: 'Status' },
          { key: 'actions:edit,delete', label: 'Action' }
        ];"""
content = content.replace(old2, new2)

# 3. Unit
old3 = """      case 'unit':
        return [
          { key: 'unitName', label: 'Unit Name' },
          { key: 'metric', label: 'Metric' },
          { key: 'notes', label: 'Notes' },
          { key: 'status', label: 'Status' },
          { key: 'actions:edit,delete', label: 'Action' }
        ];"""
new3 = """      case 'unit':
        return [
          { key: 'unitCode', label: 'Unit Code' },
          { key: 'unitName', label: 'Unit Name' },
          { key: 'metric', label: 'Metric' },
          { key: 'notes', label: 'Notes' },
          { key: 'status', label: 'Status' },
          { key: 'actions:edit,delete', label: 'Action' }
        ];"""
content = content.replace(old3, new3)

# 4. Branch Product
old4 = """      case 'branch-product':
        return [
          { key: 'index', label: '#' },
          { key: 'branchName', label: 'Branch Name' },
          { key: 'branchType', label: 'Branch Type' },
          { key: 'address', label: 'Address' },
          { key: 'phone', label: 'Phone' },
          { key: 'actions:view,edit', label: 'Action' }
        ];"""
new4 = """      case 'branch-product':
        return [
          { key: 'index', label: '#' },
          { key: 'branchName', label: 'Branch Name' },
          { key: 'productName', label: 'Product Name' },
          { key: 'productCode', label: 'Product Code' },
          { key: 'locationName', label: 'Location' },
          { key: 'stock', label: 'Stock' },
          { key: 'minStock', label: 'Min Stock' },
          { key: 'maxStock', label: 'Max Stock' },
          { key: 'actions:view,edit', label: 'Action' }
        ];"""
content = content.replace(old4, new4)

# 5. Bill of Material
old5 = """      case 'bill-of-material':
        return [
          { key: 'index', label: '#' },
          { key: 'bomName', label: 'Bill of Material Name' },
          { key: 'bomCode', label: 'Bom Code' },
          { key: 'bomType', label: 'Bill of Material Type' },
          { key: 'productName', label: 'Product Name' },
          { key: 'unitName', label: 'Unit' },
          { key: 'notes', label: 'Notes' },
          { key: 'status', label: 'Status' },
          { key: 'actions:view,edit,delete', label: 'Action' }
        ];"""
new5 = """      case 'bill-of-material':
        return [
          { key: 'index', label: '#' },
          { key: 'bomName', label: 'Bill of Material Name' },
          { key: 'bomCode', label: 'Bom Code' },
          { key: 'bomType', label: 'Bill of Material Type' },
          { key: 'productName', label: 'Product Name' },
          { key: 'unitName', label: 'Unit' },
          { key: 'outputQty', label: 'Output Qty' },
          { key: 'notes', label: 'Notes' },
          { key: 'status', label: 'Status' },
          { key: 'actions:view,edit,delete', label: 'Action' }
        ];"""
content = content.replace(old5, new5)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("LiveDataTable.tsx updated successfully.")
