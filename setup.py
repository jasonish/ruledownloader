from distutils.core import setup

VERSION = "0.1"

setup(name="ruledownloader",
      version=VERSION,
      scripts=["ruledownloader"],
      package_dir={'': "lib"},
      packages=["ruledownloader"],
)
      
