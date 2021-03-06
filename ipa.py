import argparse
import pathlib
import random
from typing import List
import re

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QPushButton, QInputDialog
from tqdm import tqdm
import eng_to_ipa as ipa

from src.utils.tsv import read_tsv, write_tsv, TSVEntry
from src.utils import round_robin_map


class SentenceWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout()
        self.checkbox = QCheckBox()
        self.eng = QLabel()
        self.ipa = QLabel()
        self.eng.setFont(QFont('Arial font', 14))
        self.ipa.setFont(QFont('Arial font', 14))
        self.layout.addWidget(self.checkbox)
        qvl = QWidget()
        vl = QVBoxLayout()
        vl.addWidget(self.eng)
        vl.addWidget(self.ipa)
        qvl.setLayout(vl)
        self.layout.addWidget(qvl)
        self.setLayout(self.layout)
        self.index = -1

    def is_wrong(self) -> bool:
        return self.checkbox.isChecked()

    def set_classification(self, eid: int, eng: str, tipa: str):
        self.index = eid
        self.eng.setText(eng)
        self.ipa.setText(tipa)
        self.checkbox.setChecked(False)


class MainWindow(QWidget):
    def __init__(self, entries: List[TSVEntry], filename: pathlib.Path):
        super().__init__()
        self.display_count = 10
        self.layout = QVBoxLayout()
        self.sentences = []
        for _ in range(self.display_count):
            q = SentenceWidget()
            self.sentences.append(q)
            self.layout.addWidget(q)
        self.submit_button = QPushButton("Finished")
        self.submit_button.clicked.connect(self.double_check)
        self.progress_status = QLabel()
        self.layout.addWidget(self.submit_button)
        self.layout.addWidget(self.progress_status)
        self.entries = list(enumerate(entries[:]))
        self.dataset = entries[:]
        self.filename = filename
        self.setLayout(self.layout)
        self.generate_next_set()

    def save_dataset(self):
        write_tsv(self.filename, self.dataset)

    def generate_next_set(self):
        if self.display_count > len(self.entries):
            entry_set = self.entries[:]
            self.entries.clear()
        else:
            entry_set = random.sample(self.entries, k=self.display_count)
            for e in entry_set:
                self.entries.remove(e)

        for e, d in zip(entry_set, self.sentences):
            index, entry = e
            d.set_classification(index, entry['sentence'], entry['ipa'])

        self.progress_status.setText('{} entires remain'.format(len(self.entries)))

    def double_check(self):
        for s in self.sentences:
            if s.is_wrong():
                tipa, done = QInputDialog.getText(self, "IPA Correction", 'IPA for "{}"'.format(s.eng.text()))
                if done:
                    s.ipa.setText(tipa)
            self.dataset[s.index]['ipa'] = s.ipa.text()
        self.save_dataset()
        self.generate_next_set()


def insert_tsv_ipa(e: TSVEntry) -> TSVEntry:
    e['ipa'] = ipa.convert(e['sentence'])
    return e


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Converts english to IPA and updates the tsv file accordingly')
    parser.add_argument('tsv_file', type=pathlib.Path, help='The file to insert ipa into')
    parser.add_argument('--batch_size', type=int, help='The number of entries to queue up on the processor',
                        default=256, required=False)

    args = parser.parse_args()

    values = read_tsv(args.tsv_file)

    if not all(map(lambda x: 'ipa' in x, tqdm(values, desc="Checking for IPA column"))):
        values = round_robin_map(values, insert_tsv_ipa, args.batch_size, 'Converting sentences to IPA')
        write_tsv(args.tsv_file, values)

    for v in tqdm(values, desc='Updating hyphenated IPA values'):
        m = re.findall(r'[a-zA-Z]+-[a-zA-Z\-\']+\*', v['ipa'])
        for mt in m:
            replacement = ''
            if '-' in mt:
                segs = mt.split('-')
                ipas = []
                for seg in segs:
                    ipas.append(ipa.convert(seg.replace('*', '')))
                replacement = '.'.join(ipas)

            if len(replacement) > 0 and '*' not in replacement:
                v['ipa'] = v['ipa'].replace(mt, replacement)

    write_tsv(args.tsv_file, values)

    # skips = set()
    removes = []
    # for v in tqdm(values, desc='Updating missing IPA values'):
    #     m = re.findall(r'[a-zA-Z\-\']+\*', v['ipa'])
    #     for mt in m:
    #         if mt in skips:
    #             removes.append(v)
    #             break
    #
    #         skip_entry = False
    #         while True:
    #             replacement = input('\nWhat is the IPA for {} from \n\t"{}"\n\t"{}"\n? '
    #                                 '(type stop to stop, or save to save, or skip to remove) '.format(mt,
    #                                                                                                   v['sentence'],
    #                                                                                                   v['ipa']))
    #             if replacement.lower() == 'stop':
    #                 print('Stopping here for now', file=sys.stderr)
    #                 for r in removes:
    #                     values.remove(r)
    #                 write_tsv(args.tsv_file, values)
    #                 errors = 0
    #                 for vt in values:
    #                     if re.search(r'[a-zA-Z\-\']+\*', vt['ipa']) is not None:
    #                         errors += 1
    #                 print('There are at least {} errors left'.format(errors), file=sys.stderr)
    #                 exit(0)
    #             elif replacement.lower() == 'save':
    #                 print('Saving current changes', file=sys.stderr)
    #                 nvalues = values[:]
    #                 for r in removes:
    #                     nvalues.remove(r)
    #                 write_tsv(args.tsv_file, nvalues)
    #                 errors = 0
    #                 for vt in nvalues:
    #                     if re.search(r'[a-zA-Z\-\']+\*', vt['ipa']) is not None:
    #                         errors += 1
    #                 print('There are at least {} errors left'.format(errors), file=sys.stderr)
    #                 continue
    #             elif replacement.lower() == 'skip':
    #                 removes.append(v)
    #                 skips.add(mt)
    #                 skip_entry = True
    #
    #             break
    #
    #         if skip_entry:
    #             break
    #
    #         v['ipa'] = v['ipa'].replace(mt, replacement)

    new_values = []
    for v in tqdm(values, desc='Filtering remaining missing translations'):
        if '*' not in v['ipa']:
            new_values.append(v)

    # for r in tqdm(removes, desc='Removing missing values'):
    #     values.remove(r)

    write_tsv(args.tsv_file, new_values)

    # app = QApplication(sys.argv)
    # v = MainWindow(values, args.tsv_file)
    # v.show()
    # app.exec()

