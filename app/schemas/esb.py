from pydantic import BaseModel, Field, ConfigDict, AliasChoices
from typing import Optional

class ESBGenericModel(BaseModel):
    """Generic model for staging data that just requires an esb_id."""
    model_config = ConfigDict(extra='allow')

class ESBBranchModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    branchID: int
    branchCode: str
    branchName: str
    locationName: Optional[str] = None
    stock: Optional[float] = None
    availableStock: Optional[float] = None

class ESBProductModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    productID: int
    productName: str
    productCode: str
    bomName: Optional[str] = None
    categoryName: Optional[str] = None
    subCategoryName: Optional[str] = None
    categoryTypeName: Optional[str] = None
    flagActive: Optional[int] = None
    barcode: Optional[str] = None
    uomName: Optional[str] = None
    purchasePrice: Optional[float] = None
    sellPrice: Optional[float] = None
    stock: Optional[float] = None
    hasVariant: Optional[bool] = None
    isRawMaterial: Optional[bool] = None
    isProduction: Optional[bool] = None
    imageUrl: Optional[str] = None

class ESBCategoryModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    categoryID: int
    categoryCode: Optional[str] = None
    categoryName: str
    categoryTypeName: Optional[str] = None
    flagActive: Optional[int] = Field(default=1)

class ESBSubCategoryModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    subCategoryID: int = Field(validation_alias=AliasChoices('id', 'subCategoryID'), default=0)
    categoryID: Optional[int] = None
    subCategoryCode: Optional[str] = None
    subCategoryName: str
    flagActive: Optional[int] = Field(default=1)

class ESBUnitModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    unitID: int = Field(validation_alias=AliasChoices('id', 'unitID', 'uomID', 'metricID'), default=0)
    unitCode: Optional[str] = Field(validation_alias=AliasChoices('unitCode', 'metricName'), default=None)
    unitName: str = Field(validation_alias=AliasChoices('unitName', 'uomName'), default="-")
    flagActive: Optional[int] = Field(default=1)

class ESBBomModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    bomID: int = Field(validation_alias=AliasChoices('id', 'bomID'), default=0)
    productID: Optional[int] = None
    bomCode: Optional[str] = None
    bomName: str
    outputQty: Optional[float] = Field(default=1.0)
    flagActive: Optional[int] = Field(default=1)
    
class ESBBranchProductModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    branchProductID: int = Field(validation_alias=AliasChoices('id', 'branchProductID'), default=0)
    branchID: int
    productID: int
    stock: Optional[float] = Field(default=0)
    availableStock: Optional[float] = Field(default=0)
    flagActive: Optional[int] = Field(default=1)

class ESBPricelistModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    pricelistID: int = Field(validation_alias=AliasChoices('id', 'pricelistID'), default=0)
    productID: int
    branchID: Optional[int] = None
    price: Optional[float] = Field(default=0)
    flagActive: Optional[int] = Field(default=1)


class ESBEmployeeModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    employeeID: int = Field(validation_alias=AliasChoices('employeeId', 'employeeID', 'id'), default=0)
    full_name: str = Field(validation_alias=AliasChoices('fullName', 'full_name'), default="Unknown")
    position: str = Field(default="STAFF")
    branch_id: str = Field(default="UNKNOWN")
    status: str = Field(default="ACTIVE")
    employeeGroup: Optional[str] = None

class ESBSupplierModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    supplierID: int = Field(validation_alias=AliasChoices('supplierId', 'supplierID', 'id'), default=0)
    name: str = Field(validation_alias=AliasChoices('supplierName', 'name'), default="Unknown")
    type: Optional[str] = Field(default="GENERAL")
    status: str = Field(default="ACTIVE")
    supplierCategory: Optional[str] = None
