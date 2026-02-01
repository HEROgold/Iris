from helpers.files import new_file, original_file, read_file


rf = open(original_file, "rb")
wf = open(new_file, "rb+")

def reset_file() -> None:
    wf.seek(0)
    read_file.seek(0)
    wf.write(read_file.read())

def test_equal() -> None:
    same = rf.read() == wf.read()
    if not same:
        reset_file()
    assert same
