import timeit

from state_effect.property_path import p

path = p.as_path(p().a["wow"][::-1])

print(path)


class X:
    a = {"wow": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]}


N = 10000
x = X()
a = timeit.timeit(lambda: path.resolve(x), number=N)
b = timeit.timeit(lambda: eval(f"x{path}"), number=N)
c = timeit.timeit(lambda: x.a["wow"][::-1], number=N)
d = timeit.timeit(lambda: getattr(x, "a").get("wow").__getitem__(slice(None, None, -1)))

print("Dyn", a)
print("Eval", b)
print("Hardcoded", c)
print("Manual f-call", d)
