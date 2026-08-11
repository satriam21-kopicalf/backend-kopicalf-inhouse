from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class ESBGenericModel(BaseModel):
    """Generic model for staging data that just requires an esb_id."""
    model_config = ConfigDict(extra='allow')
    esb_id: str = Field(..., description="ID dari ESB")

class ESBBranchModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    branchID: int
    branchCode: str
    branchName: str

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

class ESBCategoryModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    esb_id: str = Field(..., description="ID Category dari ESB lama")
    name: str = Field(..., min_length=3)
    status: str = Field(default="ACTIVE")

class ESBEmployeeModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    esb_id: str = Field(..., description="ID Employee dari ESB lama")
    full_name: str
    position: str = Field(default="STAFF")
    branch_id: str = Field(default="UNKNOWN")
    status: str = Field(default="ACTIVE")

class ESBSupplierModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    esb_id: str = Field(..., description="ID Supplier dari ESB")
    name: str = Field(..., min_length=3)
    type: Optional[str] = Field(default="GENERAL")
    status: str = Field(default="ACTIVE")
