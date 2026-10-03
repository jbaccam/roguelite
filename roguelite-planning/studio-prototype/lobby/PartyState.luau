-- Lobby parties (user, 2026-10-03: "we should be able to be in the same group so when i click
-- play he automatically gets put in a pod with me"). Server-owned and pure like QueueState: time
-- is passed in, so the rules can be tested without waiting. Players in one lobby server invite
-- each other from the Party window; a party holds up to `max` players (a portal pad's capacity).
-- RogueliteLobbyPreview puts the rest of a party on a pad as soon as one of them joins it.
-- Each player has at most one pending invite (a newer one replaces it), INVITE_SECONDS long.
-- Example: Ana invites Ben; Ben accepts -> party {Ana, Ben}. Ana presses PLAY -> both on portal 1.
local PartyState={}
PartyState.__index=PartyState
PartyState.INVITE_SECONDS=60
function PartyState.new(max)
 return setmetatable({max=max,partyOf={},invites={}},PartyState)
end
-- Everyone in id's party, id included, in join order ({id} when they aren't in one).
function PartyState:members(id)
 local party=self.partyOf[id]
 return party and table.clone(party) or {id}
end
function PartyState:size(id) local party=self.partyOf[id];return party and #party or 1 end
-- from invites to. Returns true, or false and a reason for the inviter.
function PartyState:invite(from,to,now)
 if from==to then return false,"You can't invite yourself" end
 local party=self.partyOf[from]
 if party and table.find(party,to) then return false,'Already in your party' end
 if self:size(from)>=self.max then return false,'Your party is full' end
 self.invites[to]={from=from,expires=now+PartyState.INVITE_SECONDS}
 return true
end
-- to accepts from's invite: out of any party they are in, into from's.
function PartyState:accept(to,from,now)
 local invite=self.invites[to]
 if not invite or invite.from~=from then return false,'That invite is gone' end
 self.invites[to]=nil
 if now>invite.expires then return false,'That invite expired' end
 local party=self.partyOf[from]
 if party and table.find(party,to) then return true end
 if self:size(from)>=self.max then return false,'That party is full' end
 self:leave(to)
 party=self.partyOf[from]
 if not party then party={from};self.partyOf[from]=party end
 table.insert(party,to);self.partyOf[to]=party
 return true
end
function PartyState:decline(to) self.invites[to]=nil end
-- id leaves their party; a party left with one player is no party.
function PartyState:leave(id)
 local party=self.partyOf[id];if not party then return false end
 table.remove(party,table.find(party,id));self.partyOf[id]=nil
 if #party==1 then self.partyOf[party[1]]=nil;table.clear(party) end
 return true
end
-- id left the server: out of their party, and invites sent to or by them are void.
function PartyState:remove(id)
 self:leave(id);self.invites[id]=nil
 for to,invite in self.invites do if invite.from==id then self.invites[to]=nil end end
end
-- Drops expired invites; returns true when any went away.
function PartyState:expire(now)
 local any=false
 for to,invite in self.invites do if now>invite.expires then self.invites[to]=nil;any=true end end
 return any
end
return PartyState
