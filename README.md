# VM-Manager

### Запуск

1. Запускаем БД:
        
        docker-compos e up -d

2. Запускаем сервер: 

        py.exe -m src.server.server

3. Запускаем клиент:

        py.exe .\client.py


### Команды:

ADD_USER - добавляет пользователя

LIST_USERS - выводит список пользователей

AUTH - аутентификация

ADD_VM - добавить VM

LIST_CON_VM - выводит список подключенных VM

LIST_AU_VM - выводит список аутентифицированных VM

LIST_ALL_VM - выводит список всех VM

UPDATE_VM - обновляет характеристики VM

LOGOUT_VM - выходит из VM

LIST_DISKS - список дисков