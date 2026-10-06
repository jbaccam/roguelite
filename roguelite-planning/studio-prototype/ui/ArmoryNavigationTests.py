"""Exercise extracted production Armory selection and ItemCard arrow logic with Luau CLI."""
from pathlib import Path
import subprocess
import sys
import tempfile
PRELUDE = r'''
local state={tab='Weapons'}
local weaponInfoEntries={{id='36',rarity='Godly'},{id='03',rarity='Epic'},{id='19',rarity='Common'},{id='18',rarity='Epic'},{id='08',rarity='Common'}}
local Chests={RarityOf={}}
local opts={profile=function() return {} end}
local canvas,L={},{}
local itemCard
local Card={}
'''
CHECKS = r'''
local browser=showInfo('03')
assert(browser.Id()=='03')
browser.Step(1);assert(browser.Id()=='19','navigation resorted by rarity or raw id')
browser.Step(1);assert(browser.Id()=='18','class render order lost')
browser.Step(2);assert(browser.Id()=='36','forward wrap wrong')
browser.Step(-1);assert(browser.Id()=='08','reverse wrap wrong')
-- A filter redraw replaces visible entries: no hidden weapons enter the browser.
weaponInfoEntries={{id='18',rarity='Epic'},{id='08',rarity='Common'}}
browser=showInfo('18');browser.Step(-1);assert(browser.Id()=='08')
browser.Step(-1);assert(browser.Id()=='18')
-- A details item outside the grid stays a single-item view.
browser=showInfo('99');browser.Step(1);assert(browser.Id()=='99')
state.tab='Classes';browser=showInfo('03');browser.Step(1);assert(browser.Id()=='03')
print('PASS Armory info: rendered mixed-rarity order, wrap, filtered list, non-grid fallback')
'''

base=Path(__file__).resolve().parent
armory=(base/'ArmoryUI.luau').read_text()
card=(base/'ItemCardUI.luau').read_text()
show=armory[armory.index('\tlocal function closeInfo()'):armory.index('\tself.ShowInfo = showInfo')]
nav=card[card.index(' local self={}\n',card.index('function K.open(')):card.index(' draw=function()',card.index('function K.open('))]
with tempfile.TemporaryDirectory(prefix='roguelite-armory-nav-') as directory:
    path=Path(directory)/'ArmoryNavigationTests.luau'
    path.write_text(PRELUDE+'function Card.open(canvas,L,args)\n'+nav+' draw=function() end\n return self\nend\n'+show+CHECKS)
    subprocess.run([sys.argv[1],str(path)],check=True)
