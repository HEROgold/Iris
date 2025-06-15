
import logging


stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("[ %(levelname)s ]: %(message)s"))
stream_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler("iris.log", mode="w")
file_handler.setFormatter(logging.Formatter("%(name)s [ %(levelname)s ]: %(message)s"))
file_handler.setLevel(logging.DEBUG)

iris = logging.getLogger("Iris")
iris.setLevel(1)
iris.addHandler(file_handler)
# iris.addHandler(stream_handler)

dump = logging.getLogger("Iris.Dump")
dump.addHandler(logging.FileHandler("iris.dump.log", mode="w"))
