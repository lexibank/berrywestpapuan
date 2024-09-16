import pathlib
import attr
from clldutils.misc import slug
from pylexibank import Dataset as BaseDataset
from pylexibank import progressbar as pb
from pylexibank import Language, Concept, Lexeme
from pylexibank import FormSpec
import re
import lingpy


@attr.s
class CustomConcept(Concept):
    Indonesian_Gloss = attr.ib(default=None)


@attr.s
class CustomLanguage(Language):
    Name_in_Source = attr.ib(default=None)
    ID_in_Source = attr.ib(default=None)


@attr.s
class CustomLexeme(Lexeme):
    Digital_Source = attr.ib(default=None)


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = "berrywestpapuan"
    form_spec = FormSpec(separators="~;,/", missing_data=["-"], first_form_only=True)
    concept_class = CustomConcept
    language_class = CustomLanguage
    lexeme_class = CustomLexeme

    def cmd_download(self, args):
        lines = []
        for i in range(47, 57):
            url = "https://database.outofpapua.com/sources/{0}/entries?pagesize=1000".format(i)
            self.raw_dir.download(
                    url,
                    "data-{0}.html".format(i)
                    )
            args.log.info("downloaded {0}".format(i))
            with open(self.raw_dir / "data-{0}.html".format(i)) as file:
                data = file.read()
            records = re.findall(
                    '<td><a href="([^"]*)">(.*)</a></td><td><span>(.*?)</span></td><td><p class="svelte-10l9z7a"><!-- HTML_TAG_START -->([^>]*)<!--',
                    data)
            language = re.findall(
                    '<h2>[^:]*: ([^<]*)</h2>',
                    data)[0]
            for ref, word, ipa, concept in records:
                eng, ind = concept.split("; ")
                lines += [[
                    ref, 
                    language, 
                    eng.replace(" (eng)", "")[1:-1], 
                    ind.replace(" (ind)", "")[1:-1], 
                    word, 
                    ipa]]
        with open(self.raw_dir / "data.tsv", "w") as f:
            f.write("ID\tLOCAL_ID\tLANGUAGE\tCONCEPT\tINDONESIAN\tVALUE\tFORM\n")
            for i, line in enumerate(lines):
                f.write("{0}\t".format(i + 1) + "\t".join(line) + "\n")

    def cmd_makecldf(self, args):
        # add bib
        args.writer.add_sources()
        args.log.info("added sources")

        # add concept
        concepts = {}
        for concept in self.concepts:
            idx = concept["NUMBER"] + "_" + slug(concept["ENGLISH"])
            args.writer.add_concept(
                    ID=idx,
                    Name=concept["ENGLISH"],
                    Indonesian_Gloss=concept["INDONESIAN"],
                    Concepticon_ID=concept["CONCEPTICON_ID"],
                    Concepticon_Gloss=concept["CONCEPTICON_GLOSS"]
                    )
            concepts[concept["LEXIBANK_GLOSS"]] = (idx, concept["PAGE"])

        args.log.info("added concepts")

        # add language
        languages = args.writer.add_languages(lookup_factory="Name_in_Source")
        args.log.info("added languages")

        # read in data
        data = self.raw_dir.read_csv(
            "data.tsv", delimiter="\t", dicts=True
        )
        # add data
        errors = set()
        for entry in pb(data, desc="cldfify", total=len(data)):
            if entry["CONCEPT"] in concepts:
                args.writer.add_form(
                        Parameter_ID=concepts[entry["CONCEPT"]][0],
                        Language_ID=languages[entry["LANGUAGE"]],
                        Local_ID=entry["LOCAL_ID"],
                        Value=entry["VALUE"],
                        Form=entry["FORM"].replace(" ", "_"),
                        Source="Berry1987[{0}]".format(concepts[entry["CONCEPT"]][1]),
                        Digital_Source = "https://database.outofpapua.com" + entry["LOCAL_ID"]
                        )
            else:
                errors.add(entry["CONCEPT"])
        for err in errors:
            args.log.info("Erroneous Mapping: " + err)

