from clean import clean_rows


def test_strips_and_lowercases_the_email():
    rows = clean_rows([{"name": " Asha ", "email": " ASHA@Example.com ", "age": "31"}])
    assert rows == [{"name": "Asha", "email": "asha@example.com", "age": 31}]
