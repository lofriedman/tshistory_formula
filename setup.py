from pathlib import Path
from setuptools import setup


doc = Path(__file__).parent / 'README.md'


setup(name='tshistory_formula',
      version='0.8.0',
      author='Pythonian',
      author_email='aurelien.campeas@pythonian.fr',
      url='https://hg.sr.ht/~pythonian/tshistory_formula',
      description='Computed timeseries plugin for `tshistory`',
      long_description=doc.read_text(),
      long_description_content_type='text/markdown',

      packages=['tshistory_formula'],
      zip_safe=False,
      install_requires=[
          'tshistory',
          'psyl'
      ],
      package_data={'tshistory_formula': [
          'schema.sql'
      ]},
      entry_points={'tshistory.subcommands': [
          'ingest-formulas=tshistory_formula.cli:ingest_formulas',
          'update-formula-metadata=tshistory_formula.cli:update_metadata',
          'typecheck-formula=tshistory_formula.cli:typecheck_formula',
          'test-formula=tshistory_formula.cli:test_formula',
          'formula-init-db=tshistory_formula.cli:init_db',
          'migrate-0.6-to-0.7=tshistory_formula.cli:migrate',
          'shell=tshistory_formula.cli:shell'
      ]},
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 3',
          'Topic :: Database',
          'Topic :: Scientific/Engineering',
          'Topic :: Software Development :: Version Control'
      ]
)
