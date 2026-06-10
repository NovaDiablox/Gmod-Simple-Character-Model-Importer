if SERVER then
    AddCSLuaFile()
    AddCSLuaFile("dynamic_model_importer/sh_core.lua")
end

include("dynamic_model_importer/sh_core.lua")

TOOL.Category = "#dynamic_model_importer.category"
TOOL.Name = "#tool.dynamic_model_importer_jigglebone.name"
TOOL.Command = nil
TOOL.ConfigName = ""

TOOL.ClientConVar = {
    model_path = "",
}

local function L(raw)
    return DynamicModelImporter.L(raw)
end

local function get_target(trace, owner)
    local ent = trace and trace.Entity
    if not IsValid(ent) then ent = owner end
    if IsValid(ent) and IsValid(ent.AttachedEntity) then ent = ent.AttachedEntity end
    return ent
end

local function read_convar_string(name, fallback)
    local cvar = GetConVar(name)
    if not cvar then return fallback or "" end
    return cvar:GetString()
end

local function compact_bone_name(name)
    return string.lower(tostring(name or "")):gsub("[^%w]", "")
end

local essentialBoneNames = {
    root = true,
    pelvis = true,
    hip = true,
    hips = true,
    spine = true,
    spine1 = true,
    spine2 = true,
    spine3 = true,
    spine4 = true,
    chest = true,
    upperchest = true,
    neck = true,
    neck1 = true,
    head = true,
    head1 = true,
    clavicle = true,
    lclavicle = true,
    rclavicle = true,
    leftclavicle = true,
    rightclavicle = true,
}

local function is_essential_jiggle_bone_name(name)
    local raw = string.lower(tostring(name or ""))
    if raw == "" then return false end
    if string.find(raw, "valvebiped.", 1, true) then return true end
    if string.find(raw, "valvebiped", 1, true) == 1 then return true end
    return essentialBoneNames[compact_bone_name(raw)] == true
end

local function add_essential_bones_from_entity(ent, override)
    if not IsValid(ent) or not ent.GetBoneCount or not ent.GetBoneName then return 0 end
    override.no_jiggle = override.no_jiggle or { all = false, bones = {} }
    override.no_jiggle.bones = override.no_jiggle.bones or {}
    if override.no_jiggle.all then return 0 end
    local added = 0
    for index = 0, math.max((ent:GetBoneCount() or 0) - 1, -1) do
        local name = tostring(ent:GetBoneName(index) or "")
        if is_essential_jiggle_bone_name(name) and not override.no_jiggle.bones[name] then
            override.no_jiggle.bones[name] = true
            added = added + 1
        end
    end
    return added
end

local function copy_model_override(override)
    local sanitized = DynamicModelImporter.SanitizeModelOverride(override)
    local copied = DynamicModelImporter.EmptyModelOverride()
    for key, value in pairs(sanitized.hidden_submaterials) do
        copied.hidden_submaterials[key] = value
    end
    copied.no_jiggle.all = sanitized.no_jiggle.all
    for key, value in pairs(sanitized.no_jiggle.bones) do
        copied.no_jiggle.bones[key] = value
    end
    return copied
end

local function selected_list_line(list)
    if not IsValid(list) then return nil end
    local rowIndex = list:GetSelectedLine()
    if not rowIndex then return nil end
    return list:GetLine(rowIndex)
end

local function selected_list_lines(list)
    if not IsValid(list) then return {} end
    local lines = {}
    for _, line in ipairs(list:GetSelected() or {}) do
        if IsValid(line) then
            lines[#lines + 1] = line
        end
    end
    if #lines <= 0 then
        local line = selected_list_line(list)
        if IsValid(line) then
            lines[#lines + 1] = line
        end
    end
    return lines
end

local request_override
local save_override
local valid_bone_name
local trim
local split_keyword_terms
local split_root_terms
local matches_terms
local prime_bone_entity
local collect_bone_infos
local bone_names_from_lines
local update_jigglebone_highlight

if CLIENT then
    language.Add("dynamic_model_importer.category", L("Model Importer"))
    language.Add("tool.dynamic_model_importer_jigglebone.name", L("Jigglebone tool for Imported model"))
    language.Add("tool.dynamic_model_importer_jigglebone.desc", L("Disable jigglebones for any model path."))
    language.Add("tool.dynamic_model_importer_jigglebone.0", L("Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles all jigglebones."))
end

if CLIENT then
    function valid_bone_name(name)
        name = tostring(name or "")
        if name == "" then return false end
        return not string.find(string.upper(name), "INVALIDBONE", 1, true)
    end

    function trim(value)
        return string.gsub(string.gsub(tostring(value or ""), "^%s+", ""), "%s+$", "")
    end

    function split_keyword_terms(value)
        local terms = {}
        for term in string.gmatch(tostring(value or ""), "[^,%s]+") do
            term = string.lower(trim(term))
            if term ~= "" then
                terms[#terms + 1] = term
            end
        end
        return terms
    end

    function split_root_terms(value)
        local terms = {}
        local raw = tostring(value or "")
        if string.find(raw, ",", 1, true) then
            for term in string.gmatch(raw, "[^,]+") do
                term = string.lower(trim(term))
                if term ~= "" then
                    terms[#terms + 1] = term
                end
            end
        else
            for term in string.gmatch(raw, "[^%s]+") do
                term = string.lower(trim(term))
                if term ~= "" then
                    terms[#terms + 1] = term
                end
            end
        end
        return terms
    end

    function matches_terms(value, terms)
        if #terms <= 0 then return true end
        local lowered = string.lower(tostring(value or ""))
        for _, term in ipairs(terms) do
            if string.find(lowered, term, 1, true) then
                return true
            end
        end
        return false
    end

    function prime_bone_entity(ent)
        if not IsValid(ent) then return end
        if ent.InvalidateBoneCache then pcall(function() ent:InvalidateBoneCache() end) end
        if ent.SetupBones then pcall(function() ent:SetupBones() end) end
    end

    function collect_bone_infos(ent)
        if not IsValid(ent) or not ent.GetBoneCount or not ent.GetBoneName then return {}, 0 end
        prime_bone_entity(ent)
        local boneCount = ent:GetBoneCount() or 0
        local bones = {}
        local byIndex = {}
        for index = 0, math.max(boneCount - 1, -1) do
            local name = tostring(ent:GetBoneName(index) or "")
            if valid_bone_name(name) then
                local parentIndex = -1
                if ent.GetBoneParent then
                    local ok, value = pcall(function() return ent:GetBoneParent(index) end)
                    if ok and type(value) == "number" then
                        parentIndex = value
                    end
                end
                local info = {
                    index = index,
                    name = name,
                    parent_index = parentIndex,
                    parent_name = "",
                    children = {},
                    child_names = {},
                    child_count = 0,
                    essential = is_essential_jiggle_bone_name(name),
                }
                bones[#bones + 1] = info
                byIndex[index] = info
            end
        end
        for _, boneInfo in ipairs(bones) do
            local parent = byIndex[boneInfo.parent_index]
            if parent then
                boneInfo.parent_name = parent.name
                parent.children[#parent.children + 1] = boneInfo.index
                parent.child_names[#parent.child_names + 1] = boneInfo.name
            else
                boneInfo.parent_index = -1
            end
        end
        for _, boneInfo in ipairs(bones) do
            boneInfo.child_count = #(boneInfo.children or {})
            table.sort(boneInfo.child_names, function(a, b) return tostring(a) < tostring(b) end)
        end
        table.sort(bones, function(a, b)
            return tonumber(a.index or 0) < tonumber(b.index or 0)
        end)
        return bones, boneCount
    end

    function bone_names_from_lines(lines)
        local names = {}
        local seen = {}
        for _, line in ipairs(lines or {}) do
            local name = line and line.BoneName
            if name and not seen[name] then
                seen[name] = true
                names[#names + 1] = name
            end
        end
        return names
    end

    local function jigglebone_tool_active()
        local ply = LocalPlayer()
        if not IsValid(ply) then return false end
        local weapon = ply:GetActiveWeapon()
        if not IsValid(weapon) or weapon:GetClass() ~= "gmod_tool" then return false end
        if not weapon.GetMode then return false end
        return weapon:GetMode() == "dynamic_model_importer_jigglebone"
    end

    local function selected_highlight_entities(modelPath)
        local results = {}
        local seen = {}
        local target = DynamicModelImporter.LastJiggleboneTargetEntity
        if IsValid(target) and DynamicModelImporter.EntityModelPath(target) == modelPath then
            results[#results + 1] = target
            seen[target] = true
        end
        for _, ent in ipairs(ents.GetAll() or {}) do
            if #results >= 4 then break end
            if IsValid(ent) and not seen[ent] and DynamicModelImporter.EntityModelPath(ent) == modelPath then
                results[#results + 1] = ent
                seen[ent] = true
            end
        end
        return results
    end

    local function lookup_bone_index_for_highlight(ent, boneName)
        if not IsValid(ent) then return nil end
        if ent.LookupBone then
            local index = ent:LookupBone(boneName)
            if isnumber(index) and index >= 0 then return index end
        end
        if not ent.GetBoneCount or not ent.GetBoneName then return nil end
        local wanted = string.lower(tostring(boneName or ""))
        for index = 0, math.max((ent:GetBoneCount() or 0) - 1, -1) do
            if string.lower(tostring(ent:GetBoneName(index) or "")) == wanted then
                return index
            end
        end
        return nil
    end

    local function bone_position_for_highlight(ent, index)
        if not IsValid(ent) or not index then return nil end
        if ent.GetBoneMatrix then
            local ok, matrix = pcall(function() return ent:GetBoneMatrix(index) end)
            if ok and matrix then
                local pos = matrix:GetTranslation()
                if pos and pos.x then return pos end
            end
        end
        if ent.GetBonePosition then
            local ok, pos = pcall(function()
                local position = ent:GetBonePosition(index)
                return position
            end)
            if ok and pos and pos.x then return pos end
        end
        return nil
    end

    local function draw_selected_bone_highlight(ent, boneName, color)
        local index = lookup_bone_index_for_highlight(ent, boneName)
        if not index then return end
        local pos = bone_position_for_highlight(ent, index)
        if not pos then return end

        render.DrawWireframeSphere(pos, 3.5, 10, 10, color, true)
        render.DrawSphere(pos, 1.6, 8, 8, Color(color.r, color.g, color.b, 150))

        if ent.GetBoneParent then
            local ok, parentIndex = pcall(function() return ent:GetBoneParent(index) end)
            if ok and isnumber(parentIndex) and parentIndex >= 0 then
                local parentPos = bone_position_for_highlight(ent, parentIndex)
                if parentPos then
                    render.DrawLine(parentPos, pos, color, true)
                    render.DrawWireframeSphere(parentPos, 1.8, 8, 8, Color(255, 255, 255, 180), true)
                end
            end
        end
    end

    function update_jigglebone_highlight(ownerID, modelPath, boneNames)
        modelPath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
        if not modelPath or not istable(boneNames) or #boneNames <= 0 then
            if DynamicModelImporter.JiggleboneHighlight and DynamicModelImporter.JiggleboneHighlight.owner_id == ownerID then
                DynamicModelImporter.JiggleboneHighlight = nil
            end
            return
        end
        DynamicModelImporter.JiggleboneHighlight = {
            owner_id = ownerID,
            model_path = modelPath,
            bone_names = boneNames,
            updated_at = CurTime(),
        }
    end

    hook.Add("PostDrawTranslucentRenderables", "DynamicModelImporterJiggleboneBoneHighlight", function()
        local highlight = DynamicModelImporter.JiggleboneHighlight
        if not highlight or not highlight.model_path or not istable(highlight.bone_names) or #highlight.bone_names <= 0 then return end
        if not jigglebone_tool_active() then return end

        local entities = selected_highlight_entities(highlight.model_path)
        if #entities <= 0 then return end

        render.SetColorMaterial()
        cam.IgnoreZ(true)
        for _, ent in ipairs(entities) do
            prime_bone_entity(ent)
            for index, boneName in ipairs(highlight.bone_names) do
                local color = index == 1 and Color(80, 230, 255, 255) or Color(255, 210, 80, 245)
                draw_selected_bone_highlight(ent, boneName, color)
            end
        end
        cam.IgnoreZ(false)
    end)

    function request_override(modelPath)
        modelPath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
        if not modelPath then return end
        net.Start("dynamic_model_importer_request_override")
            net.WriteString(modelPath)
        net.SendToServer()
    end

    function save_override(modelPath, override)
        modelPath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
        if not modelPath then return end
        net.Start("dynamic_model_importer_save_override")
            net.WriteString(modelPath)
            net.WriteString(util.TableToJSON(DynamicModelImporter.SanitizeModelOverride(override), false) or "{}")
        net.SendToServer()
    end

    local function select_model_path(modelPath)
        modelPath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
        if not modelPath then
            notification.AddLegacy(L("Target has no valid model path."), NOTIFY_ERROR, 3)
            return false
        end
        RunConsoleCommand("dynamic_model_importer_jigglebone_model_path", modelPath)
        request_override(modelPath)
        hook.Run("DynamicModelImporterJiggleboneTargetSelected", modelPath)
        notification.AddLegacy(
            DynamicModelImporter.LF("Selected model: %s (%s)", modelPath, DynamicModelImporter.RepairScopeLabel(modelPath)),
            NOTIFY_GENERIC,
            2
        )
        return true
    end

    function TOOL:RightClick(trace)
        local target = get_target(trace, LocalPlayer())
        local modelPath = DynamicModelImporter.EntityModelPath(target)
        DynamicModelImporter.LastJiggleboneTargetEntity = IsValid(target) and target or nil
        if modelPath then select_model_path(modelPath) end
        return true
    end

    function TOOL:LeftClick(trace)
        return true
    end
else
    local function send_override_to_player(ply, modelPath)
        if not IsValid(ply) then return end
        modelPath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
        if not modelPath then return end
        net.Start("dynamic_model_importer_send_override")
            net.WriteString(modelPath)
            net.WriteString(util.TableToJSON(DynamicModelImporter.GetModelPathOverride(modelPath), false) or "{}")
        net.Send(ply)
    end

    local function selected_or_target_model_path(tool, trace, ply)
        local targetModelPath = DynamicModelImporter.EntityModelPath(get_target(trace, ply))
        if targetModelPath then return targetModelPath end
        return DynamicModelImporter.NormalizeOverrideModelPath(tool:GetClientInfo("model_path"))
    end

    function TOOL:LeftClick(trace)
        local ply = self:GetOwner()
        local modelPath = selected_or_target_model_path(self, trace, ply)
        if not modelPath then
            DynamicModelImporter.Chat(ply, "Target has no valid model path.")
            return false
        end
        if not DynamicModelImporter.CanEditOverrides(ply) then
            DynamicModelImporter.Chat(ply, "Only admins can save Dynamic Model Importer repairs on this server.")
            return false
        end

        local override = DynamicModelImporter.GetModelPathOverride(modelPath)
        if override.no_jiggle.all then
            override.no_jiggle.all = false
            override.no_jiggle.bones = {}
            add_essential_bones_from_entity(get_target(trace, ply), override)
        else
            override.no_jiggle.all = true
            override.no_jiggle.bones = {}
        end

        DynamicModelImporter.SetModelPathOverride(modelPath, override)
        DynamicModelImporter.ApplySavedOverridesForModelPath(modelPath)
        send_override_to_player(ply, modelPath)
        DynamicModelImporter.Chat(ply, "Saved repairs for model path: %s", modelPath)
        return true
    end

    function TOOL:RightClick(trace)
        local ent = get_target(trace, self:GetOwner())
        local modelPath = DynamicModelImporter.EntityModelPath(ent)
        if not modelPath then return false end
        DynamicModelImporter.SendToolModelSelection(self:GetOwner(), "jigglebone", modelPath)
        return true
    end
end

function TOOL:Reload(trace)
    return false
end

if CLIENT then
    function TOOL.BuildCPanel(panel)
        local UI = DynamicModelImporter.UI
        panel:AddControl("Header", {
            Description = L("Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles all jigglebones.")
        })

        UI.AddSection(panel, "1. Select Target", "Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel. SheepyLord/imported models use importer scope; other targets use exact .mdl path scope.", UI.Colors.Green)

        local state = {
            model_path = DynamicModelImporter.NormalizeOverrideModelPath(read_convar_string("dynamic_model_importer_jigglebone_model_path", "")),
            preview = nil,
            bones = {},
            visible_bones = {},
            override = DynamicModelImporter.EmptyModelOverride(),
        }
        local inspectAttempt = 0
        local highlightOwnerID = "DynamicModelImporterJiggleboneHighlight_" .. tostring(panel)

        local status = vgui.Create("DLabel")
        status:SetWrap(true)
        status:SetAutoStretchVertical(true)
        status:SetTextColor(UI.Colors.Muted)
        panel:AddItem(status)

        local selected = panel:TextEntry(L("Selected model path"), "dynamic_model_importer_jigglebone_model_path")
        selected:SetEditable(false)

        UI.AddSection(panel, "2. Filter Bones", "Filters decide which bones are shown in the table. Table actions affect every row currently shown.", UI.Colors.Purple)

        local keywordLabel = vgui.Create("DLabel")
        keywordLabel:SetText(L("Keyword filter"))
        keywordLabel:SetTextColor(UI.Colors.Muted)
        keywordLabel:SizeToContents()
        panel:AddItem(keywordLabel)

        local keywordEntry = vgui.Create("DTextEntry")
        keywordEntry:SetTall(24)
        keywordEntry:SetText("")
        if keywordEntry.SetUpdateOnType then keywordEntry:SetUpdateOnType(true) end
        panel:AddItem(keywordEntry)

        local rootLabel = vgui.Create("DLabel")
        rootLabel:SetText(L("Parent/root filter"))
        rootLabel:SetTextColor(UI.Colors.Muted)
        rootLabel:SizeToContents()
        panel:AddItem(rootLabel)

        local rootEntry = vgui.Create("DTextEntry")
        rootEntry:SetTall(24)
        rootEntry:SetText("")
        if rootEntry.SetUpdateOnType then rootEntry:SetUpdateOnType(true) end
        panel:AddItem(rootEntry)

        local includeDescendants = vgui.Create("DCheckBoxLabel")
        includeDescendants:SetText(L("Include descendants"))
        includeDescendants:SetTextColor(UI.Colors.Text)
        includeDescendants:SetValue(1)
        includeDescendants:SizeToContents()
        panel:AddItem(includeDescendants)

        local hairButton = panel:Button(L("Hair"))
        local sleevesButton = panel:Button(L("Sleeves"))
        local skirtButton = panel:Button(L("Skirt"))
        local leftButton = panel:Button(L("Left side"))
        local rightButton = panel:Button(L("Right side"))
        local clearFilterButton = panel:Button(L("Clear filter"))
        UI.StyleButton(hairButton, UI.Colors.Purple)
        UI.StyleButton(sleevesButton, UI.Colors.Purple)
        UI.StyleButton(skirtButton, UI.Colors.Purple)
        UI.StyleButton(leftButton, UI.Colors.Blue)
        UI.StyleButton(rightButton, UI.Colors.Blue)
        UI.StyleButton(clearFilterButton, UI.Colors.Green)

        UI.AddSection(panel, "3. Bone Table", "Disabled jigglebones are marked in red. Locked essential skeleton bones cannot be restored to jiggle.", UI.Colors.Blue)

        local boneList = vgui.Create("DListView")
        boneList:SetTall(260)
        boneList:SetMultiSelect(true)
        boneList:AddColumn(L("Index"))
        boneList:AddColumn(L("Bone"))
        boneList:AddColumn(L("Parent"))
        boneList:AddColumn(L("Children"))
        boneList:AddColumn(L("No jiggle"))
        boneList:AddColumn(L("Essential"))
        panel:AddItem(UI.StyleList(boneList))

        local lastHighlightSignature = ""
        local nextHighlightRefresh = 0
        local function update_selected_bone_highlight(force)
            local names = bone_names_from_lines(selected_list_lines(boneList))
            local signature = tostring(state.model_path or "") .. "|" .. table.concat(names, "\n")
            if not force and signature == lastHighlightSignature then return end
            lastHighlightSignature = signature
            update_jigglebone_highlight(highlightOwnerID, state.model_path, names)
        end

        boneList.OnRowSelected = function()
            timer.Simple(0, function()
                if IsValid(panel) then update_selected_bone_highlight(true) end
            end)
        end

        boneList.Think = function()
            if CurTime() < nextHighlightRefresh then return end
            nextHighlightRefresh = CurTime() + 0.12
            update_selected_bone_highlight(false)
        end

        UI.AddSection(panel, "4. Jigglebone Actions", "Use selected-bone actions for precise fixes, table actions for every row currently shown, or bulk actions when the model should have no jiggle at all. Essential skeleton bones stay locked to no-jiggle.", UI.Colors.Orange)

        local disableBoneButton = panel:Button(L("Disable selected bone jiggle"))
        local restoreBoneButton = panel:Button(L("Restore selected bone jiggle"))
        local disableFilteredButton = panel:Button(L("Disable all bones in table"))
        local restoreFilteredButton = panel:Button(L("Restore all bones in table"))
        local disableAllButton = panel:Button(L("Disable all jiggle"))
        local restoreAllButton = panel:Button(L("Restore all jiggle"))
        UI.StyleButton(disableBoneButton, UI.Colors.Orange)
        UI.StyleButton(restoreBoneButton, UI.Colors.Green)
        UI.StyleButton(disableFilteredButton, UI.Colors.Orange)
        UI.StyleButton(restoreFilteredButton, UI.Colors.Green)
        UI.StyleButton(disableAllButton, UI.Colors.Red)
        UI.StyleButton(restoreAllButton, UI.Colors.Blue)

        local function set_status(text)
            if IsValid(status) then status:SetText(L(text or "")) end
        end

        local function set_scope_status()
            if state.model_path then
                set_status(DynamicModelImporter.RepairScopeStatus(state.model_path))
            else
                set_status("Select a model by right-clicking an NPC, ragdoll, player, prop, weapon, or viewmodel.")
            end
        end

        local function cleanup_preview()
            if IsValid(state.preview) then state.preview:Remove() end
            state.preview = nil
        end

        local function is_current_essential_bone(name)
            for _, boneInfo in ipairs(state.bones) do
                if boneInfo.name == name then
                    return boneInfo.essential == true
                end
            end
            return is_essential_jiggle_bone_name(name)
        end

        local function bone_disabled(boneInfoOrName)
            local name = istable(boneInfoOrName) and boneInfoOrName.name or boneInfoOrName
            return is_current_essential_bone(name) or state.override.no_jiggle.all or state.override.no_jiggle.bones[name] == true
        end

        local function ensure_essential_bone_overrides()
            if state.override.no_jiggle.all then return 0 end
            local added = 0
            for _, boneInfo in ipairs(state.bones) do
                if boneInfo.essential and not state.override.no_jiggle.bones[boneInfo.name] then
                    state.override.no_jiggle.bones[boneInfo.name] = true
                    added = added + 1
                end
            end
            return added
        end

        local populate_bones

        local function filter_terms()
            return split_keyword_terms(IsValid(keywordEntry) and keywordEntry:GetValue() or ""),
                split_root_terms(IsValid(rootEntry) and rootEntry:GetValue() or "")
        end

        local function filter_active()
            local keywordTerms, rootTerms = filter_terms()
            return #keywordTerms > 0 or #rootTerms > 0
        end

        local function root_match_indices(rootTerms)
            local roots = {}
            if #rootTerms <= 0 then return roots end
            for _, boneInfo in ipairs(state.bones) do
                if matches_terms(boneInfo.name, rootTerms) then
                    roots[boneInfo.index] = true
                end
            end
            return roots
        end

        local function is_descendant_of_roots(boneInfo, roots)
            if not boneInfo or not next(roots) then return false end
            local currentIndex = boneInfo.index
            local byIndex = {}
            for _, item in ipairs(state.bones) do
                byIndex[item.index] = item
            end
            local visited = {}
            while currentIndex and currentIndex >= 0 and not visited[currentIndex] do
                if roots[currentIndex] then return true end
                visited[currentIndex] = true
                local current = byIndex[currentIndex]
                if not current then break end
                currentIndex = tonumber(current.parent_index or -1)
            end
            return false
        end

        local function bone_matches_filter(boneInfo)
            local keywordTerms, rootTerms = filter_terms()
            if #keywordTerms > 0 and not matches_terms(boneInfo.name, keywordTerms) then
                return false
            end
            if #rootTerms > 0 then
                local roots = root_match_indices(rootTerms)
                if includeDescendants:GetChecked() then
                    return is_descendant_of_roots(boneInfo, roots)
                end
                return roots[boneInfo.index] == true or roots[boneInfo.parent_index] == true
            end
            return true
        end

        local function set_filter(keyword, root, descendants)
            keywordEntry:SetValue(keyword or "")
            rootEntry:SetValue(root or "")
            includeDescendants:SetValue(descendants and 1 or 0)
            if populate_bones then populate_bones() end
        end

        populate_bones = function()
            boneList:Clear()
            state.visible_bones = {}
            for _, boneInfo in ipairs(state.bones) do
                if bone_matches_filter(boneInfo) then
                    state.visible_bones[#state.visible_bones + 1] = boneInfo
                    local disabled = bone_disabled(boneInfo)
                    local line = boneList:AddLine(
                        tostring(boneInfo.index),
                        boneInfo.name,
                        tostring(boneInfo.parent_name or ""),
                        tostring(boneInfo.child_count or 0),
                        boneInfo.essential and L("locked") or (disabled and L("yes") or L("no")),
                        boneInfo.essential and L("yes") or L("no")
                    )
                    line.BoneName = boneInfo.name
                    line.BoneIndex = boneInfo.index
                    line.ParentName = boneInfo.parent_name or ""
                    line.EssentialBone = boneInfo.essential == true
                    if disabled then
                        for _, column in pairs(line.Columns or {}) do
                            if IsValid(column) and column.SetTextColor then
                                column:SetTextColor(boneInfo.essential and UI.Colors.Orange or UI.Colors.Red)
                            end
                        end
                    end
                end
            end
            update_selected_bone_highlight(true)
        end

        local function set_filter_status()
            if filter_active() then
                set_status(DynamicModelImporter.LF("%d bone(s) in table.", #state.visible_bones))
            end
        end

        keywordEntry.OnChange = function()
            populate_bones()
            set_filter_status()
        end

        rootEntry.OnChange = function()
            populate_bones()
            set_filter_status()
        end

        includeDescendants.OnChange = function()
            populate_bones()
            set_filter_status()
        end

        hairButton.DoClick = function()
            set_filter("", "ValveBiped.Bip01_Head1", true)
            set_filter_status()
        end

        sleevesButton.DoClick = function()
            set_filter("", "ValveBiped.Bip01_L_Clavicle, ValveBiped.Bip01_R_Clavicle", false)
            set_filter_status()
        end

        skirtButton.DoClick = function()
            set_filter("", "skirt, skirt_, skirtbone, skirtfront, skirtback, skirtleft, skirtright, 裙, スカート, 치마", true)
            set_filter_status()
        end

        leftButton.DoClick = function()
            set_filter("_L_, left, 左", "", false)
            set_filter_status()
        end

        rightButton.DoClick = function()
            set_filter("_R_, right, 右", "", false)
            set_filter_status()
        end

        clearFilterButton.DoClick = function()
            set_filter("", "", true)
            set_scope_status()
        end

        local function inspect_model()
            state.bones = {}
            inspectAttempt = inspectAttempt + 1
            if not state.model_path then
                set_scope_status()
                populate_bones()
                return
            end

            local liveTarget = DynamicModelImporter.LastJiggleboneTargetEntity
            if DynamicModelImporter.EntityModelPath(liveTarget) == state.model_path then
                state.bones = collect_bone_infos(liveTarget)
                if #state.bones > 0 then
                    populate_bones()
                    set_scope_status()
                    return
                end
            end

            local model = state.preview
            if IsValid(model) and model.DynamicModelImporterModelPath ~= state.model_path then
                cleanup_preview()
                model = nil
            end
            if not IsValid(model) then
                model = ClientsideModel(state.model_path, RENDERGROUP_OTHER)
            end
            if not IsValid(model) then
                set_status(string.format(L("Could not inspect model: %s"), state.model_path))
                populate_bones()
                return
            end
            model:SetNoDraw(true)
            if model.SetLOD then pcall(function() model:SetLOD(0) end) end
            model.DynamicModelImporterModelPath = state.model_path
            state.preview = model
            local bones, boneCount = collect_bone_infos(model)
            state.bones = bones
            if #state.bones <= 0 and boneCount > 0 and inspectAttempt < 8 then
                populate_bones()
                set_status("")
                timer.Simple(0.1, function()
                    if not IsValid(panel) or state.model_path ~= DynamicModelImporter.NormalizeOverrideModelPath(read_convar_string("dynamic_model_importer_jigglebone_model_path", "")) then return end
                    inspect_model()
                end)
                return
            end
            populate_bones()
            if #state.bones > 0 then
                set_scope_status()
            else
                set_status(string.format(L("Could not inspect model: %s"), state.model_path))
            end
        end

        local function load_model_path(modelPath)
            modelPath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
            if not modelPath then return end
            inspectAttempt = 0
            cleanup_preview()
            state.model_path = modelPath
            state.override = copy_model_override((DynamicModelImporter.LastModelOverrides or {})[modelPath])
            RunConsoleCommand("dynamic_model_importer_jigglebone_model_path", modelPath)
            request_override(modelPath)
            inspect_model()
        end

        local function save_current()
            if not state.model_path then
                set_scope_status()
                return
            end
            state.override = DynamicModelImporter.SanitizeModelOverride(state.override)
            ensure_essential_bone_overrides()
            save_override(state.model_path, state.override)
            populate_bones()
            set_scope_status()
        end

        local function disable_bone_names(names)
            if #names <= 0 then
                return false
            end
            if not state.override.no_jiggle.all then
                for _, name in ipairs(names) do
                    state.override.no_jiggle.bones[name] = true
                end
            end
            save_current()
            return true
        end

        local function restore_bone_names(names)
            if #names <= 0 then
                return false
            end
            local restoreSet = {}
            for _, name in ipairs(names) do
                restoreSet[name] = true
            end
            if state.override.no_jiggle.all then
                state.override.no_jiggle.all = false
                state.override.no_jiggle.bones = {}
                for _, boneInfo in ipairs(state.bones) do
                    if boneInfo.essential or not restoreSet[boneInfo.name] then
                        state.override.no_jiggle.bones[boneInfo.name] = true
                    end
                end
            else
                for _, name in ipairs(names) do
                    if not is_current_essential_bone(name) then
                        state.override.no_jiggle.bones[name] = nil
                    end
                end
            end
            save_current()
            return true
        end

        local function table_bone_names()
            if #state.visible_bones <= 0 then
                set_status("No bones in table.")
                return nil
            end
            local names = {}
            for _, boneInfo in ipairs(state.visible_bones) do
                names[#names + 1] = boneInfo.name
            end
            return names
        end

        local function selected_bone_names()
            local names = bone_names_from_lines(selected_list_lines(boneList))
            if #names <= 0 then
                set_status("No bone selected.")
                return nil
            end
            return names
        end

        disableBoneButton.DoClick = function()
            local names = selected_bone_names()
            if not names then
                return
            end
            disable_bone_names(names)
        end

        restoreBoneButton.DoClick = function()
            local names = selected_bone_names()
            if not names then
                return
            end
            restore_bone_names(names)
        end

        disableFilteredButton.DoClick = function()
            local names = table_bone_names()
            if not names then
                return
            end
            disable_bone_names(names)
            set_status(DynamicModelImporter.LF("%d table bone(s).", #names))
        end

        restoreFilteredButton.DoClick = function()
            local names = table_bone_names()
            if not names then
                return
            end
            restore_bone_names(names)
            set_status(DynamicModelImporter.LF("%d table bone(s).", #names))
        end

        disableAllButton.DoClick = function()
            state.override.no_jiggle.all = true
            state.override.no_jiggle.bones = {}
            save_current()
        end

        restoreAllButton.DoClick = function()
            state.override.no_jiggle.all = false
            state.override.no_jiggle.bones = {}
            save_current()
        end

        local targetHookID = "DynamicModelImporterJiggleboneTarget_" .. tostring(panel)
        hook.Add("DynamicModelImporterJiggleboneTargetSelected", targetHookID, load_model_path)

        local overrideHookID = "DynamicModelImporterJiggleboneOverride_" .. tostring(panel)
        hook.Add("DynamicModelImporterOverrideUpdated", overrideHookID, function(modelPath, override)
            if DynamicModelImporter.NormalizeOverrideModelPath(modelPath) ~= state.model_path then return end
            state.override = copy_model_override(override)
            populate_bones()
            set_scope_status()
        end)

        panel.OnRemove = function()
            cleanup_preview()
            update_jigglebone_highlight(highlightOwnerID, nil, nil)
            hook.Remove("DynamicModelImporterJiggleboneTargetSelected", targetHookID)
            hook.Remove("DynamicModelImporterOverrideUpdated", overrideHookID)
        end

        timer.Simple(0, function()
            if IsValid(panel) and state.model_path then
                load_model_path(state.model_path)
            else
                set_scope_status()
            end
        end)
    end
end
