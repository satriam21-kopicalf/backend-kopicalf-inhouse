from pydantic import BaseModel, Field, ConfigDict
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
    subCategoryID: int = Field(alias='id', default=0)
    categoryID: Optional[int] = None
    subCategoryCode: Optional[str] = None
    subCategoryName: str
    flagActive: Optional[int] = Field(default=1)

class ESBUnitModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    unitID: int = Field(alias='id', default=0)
    unitCode: Optional[str] = None
    unitName: str
    flagActive: Optional[int] = Field(default=1)

class ESBBomModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    bomID: int = Field(alias='id', default=0)
    productID: Optional[int] = None
    bomCode: Optional[str] = None
    bomName: str
    outputQty: Optional[float] = Field(default=1.0)
    flagActive: Optional[int] = Field(default=1)
    
class ESBBranchProductModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    branchProductID: int = Field(alias='id', default=0)
    branchID: int
    productID: int
    stock: Optional[float] = Field(default=0)
    availableStock: Optional[float] = Field(default=0)
    flagActive: Optional[int] = Field(default=1)

class ESBPricelistModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    pricelistID: int = Field(alias='id', default=0)
    productID: int
    branchID: Optional[int] = None
    price: Optional[float] = Field(default=0)
    flagActive: Optional[int] = Field(default=1)


class ESBEmployeeModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    employeeID: int = Field(alias='employeeId', default=0)
    full_name: str = Field(alias='fullName', default="Unknown")
    position: str = Field(default="STAFF")
    branch_id: str = Field(default="UNKNOWN")
    status: str = Field(default="ACTIVE")
    employeeGroup: Optional[str] = None

class ESBSupplierModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    supplierID: int = Field(alias='supplierId', default=0)
    name: str = Field(alias='supplierName', default="Unknown")
    type: Optional[str] = Field(default="GENERAL")
    status: str = Field(default="ACTIVE")
    supplierCategory: Optional[str] = None
