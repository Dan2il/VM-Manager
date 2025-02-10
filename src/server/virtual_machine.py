from pydantic import BaseModel, Field


class VirtualMachine(BaseModel):
    """Класс, представляющий собой виртуальную машину"""
    
    vm_id: int
    ram: int = Field(gt=0)
    cpu: int = Field(gt=0)
    disks: dict[int, int]

