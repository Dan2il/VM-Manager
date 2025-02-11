"""
Модуль содержит реализацию имитации VM
"""

from uuid import UUID
from pydantic import BaseModel, Field


class VirtualMachine(BaseModel):
    """Класс, представляющий собой виртуальную машину"""

    vm_id: UUID
    ram: int = Field(gt=0)
    cpu: int = Field(gt=0)
    disks: dict[UUID, int]


    def __repr__(self):
        return f"{self.vm_id}:{self.ram}:{self.cpu}:{self.disks}"

    def __str__(self):
        return (f"VM:\nid: {self.vm_id},\nram: {self.ram},\n"
                f"cpu: {self.cpu},\ndisks: {self.disks}\n")
