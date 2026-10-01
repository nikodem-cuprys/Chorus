import re, pathlib

RAW = pathlib.Path(r"D:\projcets\Chorus\.scratch\chorus\samples\raw")
OUT = pathlib.Path(r"D:\projcets\Chorus\.scratch\chorus\samples\passages")
OUT.mkdir(parents=True, exist_ok=True)

# (file id, output name, title/author, start marker, stop marker or None, target words, stress notes)
SPECS = [
    (1342, "01-pride-and-prejudice-ch1-2", "Pride and Prejudice, Chapters 1-2 - Jane Austen",
     "It is a truth universally acknowledged", "CHAPTER III", 1900,
     "Long back-and-forth between Mr and Mrs Bennet with most lines untagged; later several daughters join."),
    (11, "02-alice-mad-tea-party", "Alice's Adventures in Wonderland, Chapter VII: A Mad Tea-Party - Lewis Carroll",
     "There was a table set out under a tree", "CHAPTER VIII", 1800,
     "Four Characters in one Scene (Alice, Hatter, March Hare, Dormouse), rapid untagged exchanges, sung verse."),
    (1661, "03-holmes-scandal-in-bohemia", "The Adventures of Sherlock Holmes, A Scandal in Bohemia (opening) - Arthur Conan Doyle",
     "To Sherlock Holmes she is always", None, 1600,
     "First-person narrator (Watson) who is also a Character; dialogue with Holmes; a letter read aloud."),
    (1260, "04-jane-eyre-ch1", "Jane Eyre, Chapter I - Charlotte Bronte",
     "There was no possibility of taking a walk that day", "CHAPTER II", 2000,
     "First-person child narrator; escalates from calm to fear and fury (John Reed attack); several adult Characters at the end."),
    (5200, "05-metamorphosis-opening", "Metamorphosis, Part I (opening) - Franz Kafka (tr. David Wyllie)",
     "One morning, when Gregor Samsa woke", None, 1600,
     "Long inner thoughts in quotation marks, then voices through a closed door (mother, father, sister, chief clerk)."),
    (2554, "06-crime-and-punishment-opening", "Crime and Punishment, Part I, Chapter I (opening) - Fyodor Dostoevsky (tr. Constance Garnett)",
     "On an exceptionally hot evening early in July", None, 1600,
     "Quoted inner monologue that looks like dialogue; anxious, feverish Mood; a tense exchange with the old woman."),
]

def paragraphs(text):
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\[Illustration(?:[^\[\]]|\[[^\[\]]*\])*\]", "", text)
    return [re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

index = []
for gid, name, title, start, stop, target, notes in SPECS:
    text = (RAW / f"pg{gid}.txt").read_text(encoding="utf-8")
    i = text.index(start)
    body = text[i:]
    if stop:
        j = body.find(stop)
        if j > 0:
            body = body[:j]
    out, words = [], 0
    for p in paragraphs(body):
        out.append(p)
        words += len(p.split())
        if words >= target:
            break
    header = (f"# {title}\n# Source: Project Gutenberg eBook #{gid}, https://www.gutenberg.org/ebooks/{gid}\n"
              f"# License: public domain in the USA (Project Gutenberg License; see gutenberg.org/policy/license)\n"
              f"# Words: {words}\n# Stresses: {notes}\n\n")
    (OUT / f"{name}.txt").write_text(header + "\n\n".join(out) + "\n", encoding="utf-8")
    index.append((name, words))
for n, w in index:
    print(n, w)
