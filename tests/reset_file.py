from helpers.files import original_file, new_file, read_file

rf = open(original_file, "rb")
wf = open(new_file, "rb+")

def reset_file():
    wf.seek(0)
    read_file.seek(0)
    wf.write(read_file.read())

def test_equal():
    same = rf.read() == wf.read()
    if not same:
        reset_file()
    assert same
