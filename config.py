safe_name = set('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_')

ping_config = {
    "frequency": 60,  # s
    "interval": 200,  # ms
    "timeout": 1000,  # ms
    "count": 10,
}

mtr_config = {
    "frequency": 60 * 60,  # s
    "interval": 200,  # ms
    "timeout": 1000,  # ms
    "count": 5,
    "max_ttl": 30
}


def get_config():
    return {
               "frequency": ping_config["frequency"] * 1000 * 1000 * 1000,
               "interval": ping_config["interval"] * 1000 * 1000,
               "timeout": ping_config["timeout"] * 1000 * 1000,
               "count": ping_config["count"]
           }, {
               "frequency": mtr_config["frequency"] * 1000 * 1000 * 1000,
               "interval": mtr_config["interval"] * 1000 * 1000,
               "timeout": mtr_config["timeout"] * 1000 * 1000,
               "count": mtr_config["count"],
               "max_ttl": mtr_config["max_ttl"]
           }
