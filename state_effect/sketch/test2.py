def __setattr__(self, key, value):
    print("CALLED SETATTR")
    super().__setattr__(key, value)


class A:
    ...


a = A()
A.__setattr__ = __setattr__

a.a = 10
a.b = 20

if __name__ == '__main__':
    ...
