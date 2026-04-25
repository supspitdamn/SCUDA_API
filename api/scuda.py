import fastapi
import api.schemas
import api.database
app = fastapi.FastAPI(debug=True, title = "СКУД API система")

# Сервисная часть

@app.post("/service/check-access", tags=["Service"])
async def check_access():
    pass

@app.post("/service/process_access", tags = ["Service"])
async def proccess_access():
    pass

# Часть админа

# добавление нового

@app.post("/admin/add-employee", tags=["Admin"], response_model=api.schemas.EmployeeCreate)
async def add_employee(emp: api.schemas.EmployeeCreate):
    pass

@app.post("/admin/add-room", tags = ["Admin"], response_model=api.schemas.RoomCreate)
async def add_room(emp: api.schemas.RoomCreate):
    pass

@app.post("/admin/add-access-point", tags = ["Admin"], response_model = api.schemas.CreateAccessPoint)
async def add_access_point(emp: api.schemas.CreateAccessPoint):
    pass

# Методы удаления

@app.delete("/admin/remove-employee", tags = ["Admin"])
async def delete_employee():
    pass

@app.delete("/admin/remove-room", tags = ["Admin"])
async def delete_room():
    pass

@app.delte("/admin/remove-access-point", tags = ["Admin"])
async def delete_access_point():
    pass

# Просмотр логов

@app.get("/admin/viewlogs", tags = ["Admin"])
async def view_logs():
    pass

# Назначение уровня доступа

@app.patch("/admin/restrict-access", tags= ["Admin"])
async def restrict_access():
    pass
