from setuptools import setup


setup(name='tshistory_formula',
      version='0.1.0',
      author='Pythonian',
      author_email='aurelien.campeas@pythonian.fr',
      url='https://bitbucket.org/pythonian/tshistory_formula',
      description='Computed timeseries plugin for `tshistory`',

      packages=['tshistory_formula'],
      install_requires=[
          'tshistory',
          'psyl',
          'tshistory_alias'
      ],
      entry_points={'tshistory.subcommands': [
          'convert-aliases=tshistory_formula.cli:convert_aliases',
          'compare-aliases=tshistory_formula.cli:compare_aliases',
          'ingest-formulas=tshistory_formula.cli:ingest_formulas',
          'update-formula-metadata=tshistory_formula.cli:update_metadata',
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
