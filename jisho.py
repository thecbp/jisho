import requests
from itertools import zip_longest

from bs4 import BeautifulSoup

import kana

class Jisho:
    """A class to interface with Jisho.org and store search results for use.

    """

    def __init__(self):
        self.html = None
        self.response = None
        
    def kana_to_halpern(self, untrans):
        """Take a word completely in hiragana or katakana and translate it into romaji"""
        halpern = []
        while untrans:

            if len(untrans) > 1:
                first = untrans[0]
                second = untrans[1]
            else:
                first = untrans[0]
                second = None

            if first in kana.hiragana:
                if second and second in ["ゃ", "ゅ", "ょ"]:
                    halpern.append(kana.hira2eng[first+second])
                    untrans = untrans[2:]
                else:
                    halpern.append(kana.hira2eng[first])
                    untrans = untrans[1:]
            else:
                if second and second in ["ャ", "ュ", "ョ"]:
                    halpern.append(kana.kata2eng[first+second])
                    untrans = untrans[2:]
                else:
                    halpern.append(kana.kata2eng[first])
                    untrans = untrans[1:]

            del first
            del second

        return "".join(halpern)

    def contains_kana(self, word):
        """Takes a word and returns true if there are hiragana or katakana present within the word"""
        for k in word:
            if k in kana.hiragana or k in kana.katakana or k in kana.small_characters:
                return True
        return False

    def _get_search_response(self, word="", filters=["words"]):
        """Takes a word, stores it within the Jisho object, and returns parsed HTML"""
        base_url = r"https://jisho.org/search/"
        
        # Take all the filters and append them to the base_url
        base_url += word
        for filter in filters:
            base_url += r"%20%23" + filter

        self.response = requests.get(base_url + word, timeout=5)
        return self.response

    def _extract_html(self):
        """With the response, extract the HTML and store it into the object."""
        self.html = BeautifulSoup(self.response.content, "html.parser")
        return self.html
    
    def search(self, word, filters=["words"], depth="shallow"):
        """Take a word and spit out well-formatted dictionaries for each entry.
        
        """
        
        self._get_search_response(word, filters)
        self._extract_html()

        results = self.html.find_all(class_="concept_light clearfix")
        fmtd_results = []  

        if depth == "shallow":
            for r in results:
                fmtd_results.append(self._extract_dictionary_information(r))

        elif depth == "deep":
            
            for r in results:
                fmtd_results.append(self._extract_dictionary_information(r)) 

            # If there are more than 20 results on the page, there is no "More Words" link
            more = self.html.find(class_="more")

            while more:
                link = more.get("href")
                response = requests.get(r"http:" + link, timeout=5)
                html = BeautifulSoup(response.content, "html.parser")
                results = html.find_all(class_="concept_light clearfix")

                for r in results:
                    fmtd_results.append(self._extract_dictionary_information(r))
                
                more = html.find(class_="more")

        return fmtd_results

    def _isolate_meanings(self, meanings_list):
        """Take the meanings list from the DOM and clean out non-informative meanings."""

        index = self._get_meaning_cutoff_index(meanings_list)

        if index:
            return [m for i, m in enumerate(meanings_list) if i < index]
        else:
            return meanings_list

    def _get_meaning_cutoff_index(self, meanings_list):
        """Takes a meaning list and extracts all the non Wiki, note, or non-definition entries."""
        try:
            wiki_index = [m.text == "Wikipedia defintiion" for m in meanings_list].index(True)
        except ValueError:
            wiki_index = False

        try:
            other_forms_index = [m.text == "Other forms" for m in meanings_list].index(True)
        except ValueError:
            other_forms_index = False

        try:
            notes_index = [m.text == "Notes" for m in meanings_list].index(True)
        except ValueError:
            notes_index = False
        
        if wiki_index:
            return wiki_index
        elif other_forms_index:
            return other_forms_index
        elif notes_index:
            return notes_index
        else:
            return None

    def _extract_dictionary_information(self, entry):
        """Take a dictionary entry from Jisho and return all the necessary information."""
        # Clean up the furigana for the result
        furigana = "".join([f.text for f in entry.find_all(class_="kanji")])

        # Cleans the vocabulary word for the result
        vocabulary = self._get_full_vocabulary_string(entry)
        
        # Grab the difficulty tags for the result
        diff_tags = [m.text for m in entry.find_all(class_="concept_light-tag label")]

        # Grab each of the meanings associated with the result
        cleaned_meanings = self._isolate_meanings(entry.find(class_="meanings-wrapper"))
        meanings = [m.find(class_="meaning-meaning") for m in cleaned_meanings]
        meanings_texts = [m.text for m in meanings if m != None]

        # Romanize the furigana
        # halpern = self.kana_to_halpern(furigana)

        information = {
            "furigana": furigana,
            "vocabulary": vocabulary,
            "difficulty_tags": diff_tags,
            "meanings": dict(zip(range(1,len(meanings_texts)+1),meanings_texts)),
            "n_meanings": len(meanings_texts),
            #"halpern": halpern
        }

        return information

    def _get_full_vocabulary_string(self, html):
        """Return the full furigana of a word from the html."""
        # The kana represntation of the Jisho entry is contained in this div
        text_markup = html.find(class_="concept_light-representation")

        upper_furigana = text_markup.find(class_="furigana").find_all('span')
        inset_furigana = text_markup.find(class_="text").children

        # inset_furigana needs more formatting due to potential bits of kanji sticking together
        inset_furigana_list = []
        for f in inset_furigana:
            cleaned_text = f.string.replace("\n", "").replace(" ", "") 
            if cleaned_text == "":
                continue
            elif len(cleaned_text) > 1:
                for s in cleaned_text:
                    inset_furigana_list.append(s)
            else:
                inset_furigana_list.append(cleaned_text)

        children = zip_longest(upper_furigana, inset_furigana_list)
 
        full_word = []
        for c in children:
            if c[0].text != '':
                full_word.append(c[0].text)
            elif c[0].text == '' and self.contains_kana(c[1]):
                full_word.append(c[1])
            else:
                continue
                
        print(''.join(full_word))
        print("====")
        return ''.join(full_word)

    def export_to_json(self):
        pass