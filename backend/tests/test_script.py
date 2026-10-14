import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chorus.app import create_app
from chorus.importing import Block, Span
from chorus.importing.txt import read_txt
from chorus.languages import get_pack
from chorus.models import Chapter
from chorus.script import _chapter_lines, choose_pairs, passage_of, split

SAMPLES = Path(__file__).resolve().parents[2] / ".scratch" / "chorus" / "samples"
PROTOTYPE_LINES = SAMPLES.parent / "prototypes" / "attribution" / "lines"
GUTENBERG_EPUB = SAMPLES / "import" / "pride-and-prejudice-gutenberg.epub"
PAIRS = get_pack("en").quotation.pairs


def para(text: str, type: str = "paragraph", **kw) -> Block:
    return Block(type, [Span(text)], **kw)


def cut(*blocks: Block, pairs=PAIRS) -> list[tuple[str, str]]:
    return [(line.kind, line.text) for line in split([(b, passage_of(b)) for b in blocks], pairs)]


# ---- Line splitting ----


def test_quotations_and_the_narration_between_them():
    assert cut(para("“My dear,” said his lady, “have you heard?” He had not.")) == [
        ("quote", "“My dear,”"),
        ("narration", "said his lady,"),
        ("quote", "“have you heard?”"),
        ("narration", "He had not."),
    ]


def test_a_speech_of_several_paragraphs_is_one_quotation():
    # English convention: each paragraph opens with the mark, and only the last one closes.
    lines = cut(
        para("“It was a dark night,” he began. “The wind howled."),
        para("“And then the door opened."),
        para("“Nobody was there.”"),
        para("She shivered."),
    )
    assert lines == [
        ("quote", "“It was a dark night,”"),
        ("narration", "he began."),
        ("quote", "“The wind howled.\n“And then the door opened.\n“Nobody was there.”"),
        ("narration", "She shivered."),
    ]


def test_the_same_with_straight_marks():
    assert cut(para('"One.'), para('"Two."'), para("Done.")) == [
        ("quote", '"One.\n"Two."'),
        ("narration", "Done."),
    ]


def test_a_song_inside_a_speech_stays_in_the_quotation():
    # Alice, chapter VII: the song has no double marks, and the speech closes after it.
    lines = cut(
        para("“I had to sing"),
        para("‘Twinkle, twinkle, little bat!’"),
        para("You know the song, perhaps?”"),
        para("“I’ve heard something like it,” said Alice."),
    )
    assert lines == [
        ("quote", "“I had to sing\n‘Twinkle, twinkle, little bat!’\nYou know the song, perhaps?”"),
        ("quote", "“I’ve heard something like it,”"),
        ("narration", "said Alice."),
    ]


def test_an_unclosed_quotation_ends_with_its_paragraph():
    # The next mark opens a new quotation, so the first one was never closed.
    assert cut(para("“Wait for me"), para("He ran."), para("“Too late,” she said.")) == [
        ("quote", "“Wait for me"),
        ("narration", "He ran."),
        ("quote", "“Too late,”"),
        ("narration", "she said."),
    ]


def test_an_open_quotation_looks_only_a_few_paragraphs_ahead():
    blocks = [para("“Wait"), *(para("Narration.") for _ in range(3)), para("Then.”")]
    assert cut(*blocks)[0] == ("quote", "“Wait")


def test_a_section_break_ends_an_open_quotation():
    lines = cut(para("“Wait"), Block("section_break", []), para("“Later.”"))
    assert lines == [("quote", "“Wait"), ("quote", "“Later.”")]


def test_a_letter_block_stays_whole_and_a_letter_read_aloud_is_dialogue():
    lines = cut(
        para("Dear Sir, I was told “never” and I obey.", type="letter"),
        para("“Dear Sir,” she read aloud, “I was told never.”"),
    )
    assert lines == [
        ("narration", "Dear Sir, I was told “never” and I obey."),
        ("quote", "“Dear Sir,”"),
        ("narration", "she read aloud,"),
        ("quote", "“I was told never.”"),
    ]


def test_single_marks_with_apostrophes():
    pairs = get_pack("en").quotation.alternative_pairs
    lines = cut(para("‘Don’t go,’ said the girls’ aunt. ‘It’s late.’"), pairs=pairs)
    assert lines == [
        ("quote", "‘Don’t go,’"),
        ("narration", "said the girls’ aunt."),
        ("quote", "‘It’s late.’"),
    ]


def test_single_marks_are_used_when_the_text_quotes_with_them():
    rules = get_pack("en").quotation
    british = [para("‘Hello,’ she said. ‘It’s me.’"), para("‘Oh,’ he said, “quoting”.")]
    assert choose_pairs(british, rules) == rules.alternative_pairs
    american = [para("“Hello,” she said. “It’s ‘me’.”")]
    assert choose_pairs(american, rules) == rules.pairs


def test_marks_are_kept_on_the_cut_spans():
    block = Block(
        "paragraph",
        [Span("“It was "), Span("best", ("italic",)), Span(" butter,” he said.")],
    )
    lines = split([(block, "narration")], PAIRS)
    assert [(s.text, s.marks) for s in lines[0].spans] == [
        ("“It was ", ()),
        ("best", ("italic",)),
        (" butter,”", ()),
    ]
    assert [(s.text, s.marks) for s in lines[1].spans] == [("he said.", ())]


def _quotations(work) -> list[str]:
    pairs = choose_pairs([b for c in work.chapters for b in c.blocks], get_pack("en").quotation)
    lines = split([(b, passage_of(b, matter=True)) for b in work.front_matter], pairs)
    for c in work.chapters:
        chapter = Chapter(
            title=c.title, blocks=[b.to_dict() for b in c.blocks], notes_before=[], notes_after=[]
        )
        lines += _chapter_lines(chapter, pairs)
    return [" ".join(line.text.split()) for line in lines if line.kind == "quote"]


@pytest.mark.parametrize("path", sorted((SAMPLES / "passages").glob("*.txt")), ids=lambda p: p.stem)
def test_the_sample_passages_split_like_the_prototype(path):
    """Except the Hatter's songs, which the prototype cut out of his speeches."""
    work = read_txt(path.read_bytes(), lambda _: get_pack("en").chapter_headings, path.name)
    ours = _quotations(work)
    lines = json.loads((PROTOTYPE_LINES / f"{path.stem}.json").read_text(encoding="utf-8"))
    # The prototype kept Gutenberg's underscores; the TXT reader makes them italics.
    theirs = [
        " ".join(line["text"].replace("_", "").split())
        for line in lines["lines"]
        if line["kind"] == "quote"
    ]
    assert len(ours) == len(theirs)
    differ = [(a, b) for a, b in zip(theirs, ours, strict=True) if a != b]
    if path.stem.startswith("02-alice"):
        assert [b for _, b in differ] == [
            "“—it was at the great concert given by the Queen of Hearts, and I had to sing "
            "‘Twinkle, twinkle, little bat! How I wonder what you’re at!’ "
            "You know the song, perhaps?”",
            "“in this way:— ‘Up above the world you fly, Like a tea-tray in the sky. "
            "Twinkle, twinkle—’”",
        ]
    else:
        assert differ == []


# ---- Kinds of text ----


def test_each_kind_of_block_and_whether_it_is_voiced():
    chapter = Chapter(
        title="Chapter 1",
        notes_before=[para("An author's note.").to_dict()],
        blocks=[
            para("Chapter 1", type="heading", level=2).to_dict(),
            para("Words of a poet.", type="epigraph").to_dict(),
            para("It began.").to_dict(),
            para("A quotation set apart.", type="quote").to_dict(),
            Block("section_break", []).to_dict(),
            para("Dear Sir,", type="letter").to_dict(),
            para("Twinkle, twinkle.", type="verse").to_dict(),
            para("An item", type="list_item").to_dict(),
            para("A note.", type="footnote").to_dict(),
            para("Published by Gutenberg.", boilerplate=True).to_dict(),
        ],
        notes_after=[],
    )
    lines = _chapter_lines(chapter, PAIRS)
    assert [(line.passage, line.paragraph, line.text) for line in lines] == [
        ("ao3_note", 0, "An author's note."),
        ("chapter_title", 1, "Chapter 1"),
        ("epigraph", 2, "Words of a poet."),
        ("narration", 3, "It began."),
        ("narration", 4, "A quotation set apart."),
        ("letter", 6, "Dear Sir,"),
        ("verse", 7, "Twinkle, twinkle."),
        ("list", 8, "An item"),
        ("footnote", 9, "A note."),
        ("never_voiced", 10, "Published by Gutenberg."),
    ]


def test_a_title_from_the_table_of_contents_becomes_a_line():
    chapter = Chapter(
        title="The Ball", blocks=[para("It began.").to_dict()], notes_before=[], notes_after=[]
    )
    lines = _chapter_lines(chapter, PAIRS)
    assert [(line.passage, line.paragraph, line.text) for line in lines] == [
        ("chapter_title", None, "The Ball"),
        ("narration", 0, "It began."),
    ]


def test_contents_lists_in_the_front_matter_are_never_voiced():
    assert passage_of(para("Chapter I.", type="list_item"), matter=True) == "never_voiced"
    assert passage_of(para("It began."), matter=True) == "narration"


# ---- Through the API ----


def _lines(client, work_id: int, part: str) -> list[dict]:
    path = f"matter/{part}" if part in ("front", "back") else f"chapters/{part}"
    return client.get(f"/api/works/{work_id}/{path}").json()["lines"]


def test_the_gutenberg_epub_script():
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/works", files={"file": ("pride.epub", GUTENBERG_EPUB.read_bytes())}
        )
        work = client.get(f"/api/works/{response.json()['id']}").json()
        front = _lines(client, work["id"], "front")
        assert (front[0]["passage"], front[0]["voiced"]) == ("work_title", True)
        assert front[0]["spans"] == [{"text": "Pride and Prejudice, by Jane Austen"}]
        header = [line for line in front if line["passage"] == "never_voiced"]
        assert header and not any(line["voiced"] for line in header)

        for chapter in work["chapters"]:
            lines = _lines(client, work["id"], chapter["index"])
            title = lines[0]
            assert (title["passage"], title["voiced"]) == ("chapter_title", True), chapter
            assert title["spans"][0]["text"] == chapter["title"]
        first = _lines(client, work["id"], 1)
        assert [line["kind"] for line in first[3:6]] == ["quote", "narration", "quote"]
        assert [line["position"] for line in first] == sorted(line["position"] for line in first)

        back = _lines(client, work["id"], "back")
        assert back and all(line["passage"] == "never_voiced" for line in back)


def test_gutenberg_boilerplate_in_a_txt_file_is_never_voiced():
    with TestClient(create_app()) as client:
        raw = (SAMPLES / "raw" / "pg5200.txt").read_bytes()
        response = client.post("/api/works", files={"file": ("pg5200.txt", raw)})
        work_id = response.json()["id"]
        front, back = _lines(client, work_id, "front"), _lines(client, work_id, "back")
        assert front[0]["passage"] == "work_title"
        assert front[-1]["spans"][0]["text"].startswith("*** START OF THE PROJECT GUTENBERG")
        assert back[0]["spans"][0]["text"].startswith("*** END OF THE PROJECT GUTENBERG")
        for line in front[1:] + back:
            assert (line["passage"], line["voiced"]) == ("never_voiced", False)
