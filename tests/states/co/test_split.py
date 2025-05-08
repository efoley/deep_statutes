import tempfile

from deep_statutes.pdf.parse import find_headers
from deep_statutes.states.co.split import HEADER_GRAMMAR, HEADER_TYPES

PART_7_FRAGMENT = """
<<LINE (35, 0, 0)>>
<<INDENT>>
<<INDENT>>
<<INDENT>>
<<INDENT>>
<<INDENT>>
<<INDENT>>
<<SPAN_M>>
PART 7
<<LINE (35, 1, 0)>>
<<INDENT>>
<<INDENT>>
<<INDENT>>
<<INDENT>>
<<SPAN_M>>
ENACTMENT OF LAWS REGARDING
<<LINE (35, 1, 1)>>
<<INDENT>>
<<INDENT>>
<<INDENT>>
<<SPAN_M>>
SENTENCING OF CRIMINAL OFFENDERS
<<LINE (35, 2, 0)>>
<<INDENT>>
<<SPAN_M_B>>
2-2-701.  General assembly - bills regarding the sentencing of criminal offenders -
<<LINE (35, 2, 1)>>
<<SPAN_M_B>>
legislative intent - definition.
<<LINE (35, 3, 0)>>
<<INDENT>>
<<SPAN_M>>
(1) and (2)  Repealed.
<<LINE (35, 3, 1)>>
<<INDENT>>
<<SPAN_M>>
(3)  On and after July 1, 1994, any bill which is introduced at any session of the general
<<LINE (35, 3, 2)>>
<<SPAN_M>>
"""


def test_parse_part_7_with_newline():
    with tempfile.NamedTemporaryFile('w') as temp_file:
        temp_file.write(PART_7_FRAGMENT)
        temp_file.flush()

        # Parse the headers from the temporary file
        toc = find_headers(HEADER_GRAMMAR, HEADER_TYPES, temp_file.name)

    assert len(toc.headers) == 2
    assert toc.headers[0].text == "PART 7"
    assert toc.headers[0].sub_text == "ENACTMENT OF LAWS REGARDING SENTENCING OF CRIMINAL OFFENDERS"
    assert toc.headers[1].text == "2-2-701"
    assert toc.headers[1].sub_text == "General assembly - bills regarding the sentencing of criminal offenders - legislative intent - definition."
