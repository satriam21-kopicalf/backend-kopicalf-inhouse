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
    categoryName: str
    status: str = Field(default="ACTIVE")

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
