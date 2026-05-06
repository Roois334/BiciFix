import os
class Config:
    SECRET_KEY     = os.environ.get('SECRET_KEY', 'bicifix-clave-secreta-2026')
    MYSQL_HOST     = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER     = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '0000')
    MYSQL_DB       = os.environ.get('MYSQL_DB', 'bicifix')
    MYSQL_PORT     = int(os.environ.get('MYSQL_PORT', 3306))
