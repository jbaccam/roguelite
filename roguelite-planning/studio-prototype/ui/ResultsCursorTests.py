"""Run production UITheme cursor lifecycle with mocked Roblox render/input events."""
from pathlib import Path
import subprocess
import sys
import tempfile
PRELUDE = r'''

local function signal()
 local listeners={}
 return {Connect=function(_,fn) local c={fn=fn};listeners[c]=true;return {Disconnect=function() listeners[c]=nil end} end,
 Fire=function() for c in listeners do c.fn() end end}
end
local callbacks={}
local Run={BindToRenderStep=function(_,key,_,fn) callbacks[key]=fn end,UnbindFromRenderStep=function(_,key) callbacks[key]=nil end}
local Input={MouseBehavior='Locked',MouseIconEnabled=false}
local Gui={}
local game={GetService=function(_,name) return ({RunService=Run,UserInputService=Input,GuiService=Gui})[name] end}
local Enum={MouseBehavior={Default='Default'},RenderPriority={Camera={Value=200}}}
local UDim2={fromOffset=function() return {} end}
local T={make=function(_,_,props) return props end,cameraHeal=function() end}
local changed=signal()
local screen={Parent={},Enabled=false,AncestryChanged=signal(),Destroying=signal(),GetPropertyChangedSignal=function() return changed end}
local function frame() Input.MouseBehavior='Locked';Input.MouseIconEnabled=false;for _,fn in callbacks do fn() end end
'''
CHECKS = r'''

local dispose=T.freeMenuCursor(screen)
assert(next(callbacks)==nil,'hidden menu bound input')
screen.Enabled=true;changed.Fire();frame()
assert(Input.MouseBehavior=='Default' and Input.MouseIconEnabled,'camera recaptured results cursor')
local selected={IsDescendantOf=function(_,ancestor) return ancestor==screen end};Gui.SelectedObject=selected
screen.Enabled=false;changed.Fire();frame()
assert(Input.MouseBehavior=='Locked' and Gui.SelectedObject==nil and next(callbacks)==nil,'hide leaked cursor or selection')
screen.Enabled=true;changed.Fire();frame()
assert(Input.MouseBehavior=='Default','reopen failed')
local other={IsDescendantOf=function() return false end};Gui.SelectedObject=other
screen.Parent=nil;screen.AncestryChanged.Fire();frame()
assert(next(callbacks)==nil and Gui.SelectedObject==other,'detach cleared another screen selection or leaked binding')
screen.Parent={};screen.AncestryChanged.Fire();frame()
assert(Input.MouseBehavior=='Default','reparent failed')
screen.Destroying.Fire();dispose();frame()
assert(next(callbacks)==nil and Input.MouseBehavior=='Locked','destroy leaked input')
print('PASS results cursor: hidden/show/reopen/hide/reparent/destroy, camera ordering and scoped selection')
'''

source=(Path(__file__).resolve().parent/'UITheme.luau').read_text()
helper=source[source.index('local cursorSerial=0'):source.index('-- An FOV tween')]
with tempfile.TemporaryDirectory(prefix='roguelite-cursor-') as directory:
    path=Path(directory)/'ResultsCursorTests.luau'
    path.write_text(PRELUDE+helper+CHECKS)
    subprocess.run([sys.argv[1],str(path)],check=True)
