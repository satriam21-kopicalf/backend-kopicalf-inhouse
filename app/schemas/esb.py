"""
ESB Pydantic models — sesuai response API faktual (diaudit Agustus 2026).

Catatan field aktual per endpoint:
- GET /product/list       → productID, productName, productCode, categoryID, categoryName,
                            subCategoryID, subCategoryName, bomID, bomName, categoryTypeID,
                            categoryTypeName, flagActive
- GET /product/category   → categoryID, categoryName, categoryTypeID, categoryTypeName, notes, flagActive
- GET /product/sub-category → subCategoryID, subCategoryName, notes, deadStockThreshold, flagActive
- GET /units              → metricID, metricName, uomID, uomName, flagActive, notes
- GET /pricelist          → ID, pricelistNum, priceDate, supplierID, supplierName, productDetailID,
                            productID, productName, productCode, uomID, unit, currencyID,
                            currencyName, expireDate, price, applicableBranch
- GET /product/bom        → bomID, bomName, bomCode, bomTypeID, bomTypeName, productName,
                            uomName, notes, flagActive
- GET /product/stock-location (requires productDetailID) →
                            productDetailID, productName, uomName, qty, stockQty, dropdownProduct
- GET /customer-pricelist → ID, priceDate, customerName, productName, productCode,
                            uomName, currencyName, expireDate, price
- GET /branch             → branchID, branchCode, branchName, ...
- GET /employee           → employeeID, fullName, position, branchID, status, ...
- GET /supplier           → supplierID, supplierName, type, supplierCategory, ...
"""
from pydantic import BaseModel, Field, ConfigDict, AliasChoices
from typing import Optional, Any


class ESBGenericModel(BaseModel):
    """Generic model untuk staging data yang hanya butuh esb_id."""
    model_config = ConfigDict(extra='allow')


# ─────────────────────────────────────────────
# A. PRODUCT MASTER DATA
# ─────────────────────────────────────────────

class ESBProductModel(BaseModel):
    """GET /product/list — field aktual dari audit API."""
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    productID: int
    productName: str
    productCode: str = Field(default="")
    # Category
    categoryID: Optional[int] = None
    categoryName: Optional[str] = None
    subCategoryID: Optional[int] = None
    subCategoryName: Optional[str] = None
    categoryTypeID: Optional[int] = None
    categoryTypeName: Optional[str] = None
    # BOM
    bomID: Optional[int] = None
    bomName: Optional[str] = None
    # Flags
    flagActive: Optional[int] = Field(default=1)
    # Fields mungkin ada di response lain (jadikan Optional semua)
    productAlias: Optional[str] = None
    barcode: Optional[str] = None
    uomID: Optional[int] = None
    uomName: Optional[str] = None
    pricelistID: Optional[int] = None
    purchasePrice: Optional[float] = None
    sellPrice: Optional[float] = None
    minStock: Optional[float] = None
    maxStock: Optional[float] = None
    stock: Optional[float] = None
    hasVariant: Optional[bool] = None
    isRawMaterial: Optional[bool] = None
    isProduction: Optional[bool] = None
    isTrackInventory: Optional[bool] = None
    imageUrl: Optional[str] = None
    description: Optional[str] = None


class ESBCategoryModel(BaseModel):
    """GET /product/category — field aktual: categoryID, categoryName, categoryTypeID, categoryTypeName, notes, flagActive."""
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    categoryID: int
    categoryName: str
    categoryTypeID: Optional[int] = None
    categoryTypeName: Optional[str] = None
    notes: Optional[str] = None
    flagActive: Optional[int] = Field(default=1)
    # Tidak ada di response tapi biarkan Optional untuk kompatibilitas
    categoryCode: Optional[str] = None


class ESBSubCategoryModel(BaseModel):
    """GET /product/sub-category — field aktual: subCategoryID, subCategoryName, notes, deadStockThreshold, flagActive.
    CATATAN: categoryID TIDAK ADA di response list endpoint ini.
    """
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    subCategoryID: int
    subCategoryName: str
    notes: Optional[str] = None
    deadStockThreshold: Optional[int] = None
    flagActive: Optional[int] = Field(default=1)
    # Optional — tidak ada di list response tapi mungkin ada di detail
    categoryID: Optional[int] = None
    subCategoryCode: Optional[str] = None
    displayOrder: Optional[int] = None


class ESBUnitModel(BaseModel):
    """GET /units — field aktual: metricID, metricName, uomID, uomName, flagActive, notes."""
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    # Group satuan (metric)
    metricID: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices('metricID', 'id')
    )
    metricName: Optional[str] = None

    # Satuan spesifik (UOM)
    uomID: int = Field(
        validation_alias=AliasChoices('uomID', 'unitID', 'id')
    )
    uomName: str = Field(
        validation_alias=AliasChoices('uomName', 'unitName'),
        default="-"
    )
    notes: Optional[str] = None
    flagActive: Optional[int] = Field(default=1)

    # Alias untuk backward compat
    @property
    def unitID(self) -> int:
        return self.uomID

    @property
    def unitCode(self) -> Optional[str]:
        return self.metricName


class ESBBomModel(BaseModel):
    """GET /product/bom — field aktual: bomID, bomName, bomCode, bomTypeID, bomTypeName, productName, uomName, notes, flagActive.
    CATATAN: productID TIDAK ADA di list response.
    """
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    bomID: int = Field(
        validation_alias=AliasChoices('bomID', 'id')
    )
    bomCode: Optional[str] = None
    bomName: str
    bomTypeID: Optional[int] = None
    bomTypeName: Optional[str] = None
    productName: Optional[str] = None
    uomName: Optional[str] = None
    notes: Optional[str] = None
    flagActive: Optional[int] = Field(default=1)
    # productID tidak ada di list, jadikan Optional
    productID: Optional[int] = None
    outputQty: Optional[float] = Field(default=1.0)


class ESBPricelistModel(BaseModel):
    """GET /pricelist — field aktual:
    ID, pricelistNum, priceDate, supplierID, supplierName, productDetailID,
    productID, productName, productCode, uomID, unit, currencyID, currencyName,
    expireDate, price, applicableBranch.
    """
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    pricelistID: int = Field(
        validation_alias=AliasChoices('ID', 'id', 'pricelistID'),
        default=0
    )
    pricelistNum: Optional[str] = None
    priceDate: Optional[str] = Field(
        validation_alias=AliasChoices('priceDate', 'price_date'),
        default=None
    )
    supplierID: Optional[int] = None
    supplierName: Optional[str] = None
    productDetailID: Optional[int] = None
    productID: int = Field(
        validation_alias=AliasChoices('productID', 'product_id'),
        default=0
    )
    productName: Optional[str] = None
    productCode: Optional[str] = None
    uomID: Optional[int] = None
    unitName: Optional[str] = Field(
        validation_alias=AliasChoices('unit', 'unitName', 'uomName'),
        default=None
    )
    currencyID: Optional[int] = None
    currency: Optional[str] = Field(
        validation_alias=AliasChoices('currencyName', 'currency'),
        default=None
    )
    expiredDate: Optional[str] = Field(
        validation_alias=AliasChoices('expireDate', 'expiredDate', 'expired_date'),
        default=None
    )
    price: Optional[float] = Field(default=0)
    flagActive: Optional[int] = Field(default=1)
    applicableBranch: Optional[Any] = None

    @property
    def branchID(self) -> Optional[int]:
        """Ambil branchID dari applicableBranch jika ada."""
        if isinstance(self.applicableBranch, dict):
            branches = self.applicableBranch.get('branches', [])
            if branches and isinstance(branches[0], dict):
                return branches[0].get('branchID')
        return None


class ESBBranchProductModel(BaseModel):
    """GET /product/stock-location (param: productDetailID) — field aktual:
    productDetailID, productName, uomName, qty, stockQty, dropdownProduct.
    CATATAN: Tidak ada branchID/branchName di response ini. Ini stok agregat per productDetailID.
    """
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    productDetailID: int = Field(
        validation_alias=AliasChoices('productDetailID', 'id', 'branchProductID'),
        default=0
    )
    productName: Optional[str] = None
    uomName: Optional[str] = None
    qty: Optional[float] = Field(default=1)
    stockQty: Optional[float] = Field(default=0)
    dropdownProduct: Optional[str] = None
    # Tidak ada di response tapi biarkan Optional
    productID: Optional[int] = None
    productCode: Optional[str] = None
    branchID: Optional[int] = None
    branchName: Optional[str] = None
    locationID: Optional[int] = None
    locationName: Optional[str] = None
    stock: Optional[float] = Field(default=0)
    minStock: Optional[float] = Field(default=0)
    maxStock: Optional[float] = Field(default=0)
    reservedStock: Optional[float] = Field(default=0)
    availableStock: Optional[float] = Field(default=0)
    flagActive: Optional[int] = Field(default=1)


# ─────────────────────────────────────────────
# B. BRANCH / OUTLET
# ─────────────────────────────────────────────

class ESBBranchModel(BaseModel):
    """GET /branch — field aktual dari dokumentasi ESB."""
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    branchID: int
    branchCode: str = Field(default="")
    branchName: str
    branchType: Optional[str] = None
    areaID: Optional[int] = None
    areaName: Optional[str] = None
    brandID: Optional[int] = None
    brandName: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    isActive: Optional[bool] = Field(default=True)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Compat
    locationName: Optional[str] = None
    stock: Optional[float] = None
    availableStock: Optional[float] = None


# ─────────────────────────────────────────────
# C. EMPLOYEE & SUPPLIER
# ─────────────────────────────────────────────

class ESBEmployeeModel(BaseModel):
    """GET /employee."""
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    employeeID: int = Field(
        validation_alias=AliasChoices('employeeID', 'employeeId', 'id'),
        default=0
    )
    full_name: str = Field(
        validation_alias=AliasChoices('fullName', 'full_name', 'name'),
        default="Unknown"
    )
    position: str = Field(default="STAFF")
    branch_id: Optional[str] = Field(
        validation_alias=AliasChoices('branchID', 'branch_id'),
        default=None
    )
    status: str = Field(default="ACTIVE")
    employeeGroup: Optional[str] = None


class ESBSupplierModel(BaseModel):
    """GET /supplier."""
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    supplierID: int = Field(
        validation_alias=AliasChoices('supplierID', 'supplierId', 'id'),
        default=0
    )
    name: str = Field(
        validation_alias=AliasChoices('supplierName', 'name'),
        default="Unknown"
    )
    type: Optional[str] = Field(default="GENERAL")
    status: str = Field(default="ACTIVE")
    supplierCategory: Optional[str] = Field(
        validation_alias=AliasChoices('supplierCategoryName', 'supplierCategory'),
        default=None
    )
