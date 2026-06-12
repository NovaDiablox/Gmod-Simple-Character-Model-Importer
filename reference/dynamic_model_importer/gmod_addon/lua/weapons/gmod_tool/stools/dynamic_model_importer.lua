if SERVER then
    AddCSLuaFile()
    AddCSLuaFile("dynamic_model_importer/sh_core.lua")
end

include("dynamic_model_importer/sh_core.lua")

TOOL.Category = "#dynamic_model_importer.category"
TOOL.Name = "#tool.dynamic_model_importer.name"
TOOL.Command = nil
TOOL.ConfigName = ""

TOOL.ClientConVar = {
    selected = "",
    relation = "friendly",
    health = "100",
    weapon = "weapon_smg1",
    spawn_no_jiggle = "0",
}

local function L(raw)
    return DynamicModelImporter.L(raw)
end

if CLIENT then
    language.Add("dynamic_model_importer.category", L("Model Importer"))
    language.Add("tool.dynamic_model_importer.name", L("Dynamic Model Importer"))
    language.Add("tool.dynamic_model_importer.desc", L("Spawn MMD Character Importer models."))
    language.Add("tool.dynamic_model_importer.0", L("Select a model in the menu. Left-click the world to spawn an NPC; right-click the world to spawn a ragdoll."))
end

local function selected_model_id(tool)
    return DynamicModelImporter.NormalizeID(tool:GetClientInfo("selected"))
end

function TOOL:LeftClick(trace)
    if CLIENT then return true end
    local modelID = selected_model_id(self)
    if not modelID then return false end
    return DynamicModelImporter.SpawnFromRequest(
        self:GetOwner(),
        modelID,
        "npc",
        self:GetClientInfo("relation"),
        tonumber(self:GetClientInfo("health")) or 100,
        self:GetClientInfo("weapon"),
        trace,
        self:GetClientNumber("spawn_no_jiggle", 0) ~= 0
    )
end

function TOOL:RightClick(trace)
    if CLIENT then return true end
    local modelID = selected_model_id(self)
    if not modelID then return false end
    return DynamicModelImporter.SpawnFromRequest(
        self:GetOwner(),
        modelID,
        "ragdoll",
        self:GetClientInfo("relation"),
        tonumber(self:GetClientInfo("health")) or 100,
        self:GetClientInfo("weapon"),
        trace,
        self:GetClientNumber("spawn_no_jiggle", 0) ~= 0
    )
end

function TOOL:Reload(trace)
    if CLIENT then return true end
    return false
end

local function request_refresh()
    net.Start("dynamic_model_importer_request_list")
    net.SendToServer()
end

local function convar_string(name, fallback)
    local cvar = GetConVar(name)
    if not cvar then return fallback or "" end
    return cvar:GetString()
end

local function set_combo_value(combo, value)
    for _, row in ipairs(combo.Data or {}) do
        if row.data == value then
            combo:ChooseOption(row.value, row.id)
            return
        end
    end
end

local function entry_matches_search(entry, search)
    search = string.lower(tostring(search or ""))
    if search == "" then return true end
    local haystack = table.concat({
        tostring(entry.display_name or ""),
        tostring(entry.category_readable or ""),
        tostring(entry.model_path or ""),
        tostring(entry.model_id or ""),
    }, " "):lower()
    return string.find(haystack, search, 1, true) ~= nil
end

function TOOL.BuildCPanel(panel)
    local UI = DynamicModelImporter.UI
    panel:AddControl("Header", {
        Description = L("Shows models produced by MMD Character Importer. Select a row, then left-click the world to spawn an NPC or right-click the world to spawn a ragdoll.")
    })

    UI.AddSection(panel, "1. Model Library", "Refresh the model list, filter by name or path, then select one model row.", UI.Colors.Blue)

    local refreshButton = panel:Button(L("Refresh model list"))
    UI.StyleButton(refreshButton, UI.Colors.Blue)
    refreshButton.DoClick = request_refresh

    local search = vgui.Create("DTextEntry")
    search:SetTall(22)
    search:SetPlaceholderText(L("Search models..."))
    panel:AddItem(search)

    local modelLists = {}
    local suppressSelectionCallback = false

    local function clear_model_list_selection(list)
        if not IsValid(list) then return end
        if list.ClearSelection then
            list:ClearSelection()
        end
        for _, line in pairs(list:GetLines() or {}) do
            if IsValid(line) then
                line:SetSelected(false)
            end
        end
    end

    local function clear_other_model_lists(activeList)
        suppressSelectionCallback = true
        for _, list in ipairs(modelLists) do
            if list ~= activeList then
                clear_model_list_selection(list)
            end
        end
        suppressSelectionCallback = false
    end

    local function select_model(modelID, activeList, activeLine)
        modelID = DynamicModelImporter.NormalizeID(modelID)
        if not modelID then return end
        clear_other_model_lists(activeList)
        if IsValid(activeList) and IsValid(activeLine) then
            suppressSelectionCallback = true
            clear_model_list_selection(activeList)
            activeList:SelectItem(activeLine)
            activeLine:SetSelected(true)
            suppressSelectionCallback = false
        end
        RunConsoleCommand("dynamic_model_importer_selected", modelID)
    end

    local function create_model_list(title, legacy)
        local label = vgui.Create("DLabel")
        label:SetText(L(title))
        label:SetTextColor(legacy and UI.Colors.Purple or UI.Colors.Green)
        label:SetFont("DermaDefaultBold")
        label:DockMargin(0, 8, 0, 2)
        panel:AddItem(label)

        local list = vgui.Create("DListView")
        list:SetTall(180)
        list:SetMultiSelect(false)
        list:AddColumn(L("Model"))
        list:AddColumn(L("Category"))
        list:AddColumn(L("Model path"))
        list:AddColumn(L("PM"))

        function list:Populate(entries)
            self:Clear()
            for _, entry in ipairs(entries or {}) do
                if tobool(entry.legacy) == legacy and entry_matches_search(entry, search:GetText()) then
                    local line = self:AddLine(
                        entry.display_name or entry.model_id or "",
                        entry.category_readable or "",
                        entry.model_path or "",
                        entry.has_player_model and L("yes") or L("no")
                    )
                    line.ModelID = entry.model_id
                    line.OnMousePressed = function(row, code)
                        if code == MOUSE_LEFT or code == MOUSE_RIGHT then
                            select_model(row.ModelID, self, row)
                            return true
                        end
                    end
                end
            end
        end

        list.OnRowSelected = function(self, _, line)
            if suppressSelectionCallback then return end
            if IsValid(line) and line.ModelID then
                select_model(line.ModelID, self, line)
            end
        end

        panel:AddItem(UI.StyleList(list))
        table.insert(modelLists, list)
        return list
    end

    local manifestList = create_model_list("Manifest imported models", false)
    local legacyList = create_model_list("Legacy autorun models", true)

    UI.AddSection(panel, "2. Current Selection", "The selected model id is used by left-click and right-click spawning.", UI.Colors.Green)
    local selected = panel:TextEntry(L("Selected model id"), "dynamic_model_importer_selected")
    selected:SetEditable(false)

    UI.AddSection(panel, "3. Spawn Settings", "NPC settings affect left-click NPC spawning. Ragdoll spawning uses the selected model only.", UI.Colors.Orange)

    local noJiggleColor = UI.Colors.Orange
    local noJiggle = vgui.Create("DCheckBoxLabel")
    noJiggle:SetText(L("Spawn model without jigglebone"))
    if noJiggle.SetTextColor then
        noJiggle:SetTextColor(noJiggleColor)
    end
    if IsValid(noJiggle.Label) then
        noJiggle.Label:SetTextColor(noJiggleColor)
        noJiggle.Label:SetFont("DermaDefaultBold")
    end
    noJiggle:SetConVar("dynamic_model_importer_spawn_no_jiggle")
    noJiggle:SetValue(convar_string("dynamic_model_importer_spawn_no_jiggle", "0") == "1" and 1 or 0)
    noJiggle:SizeToContents()
    noJiggle:SetTooltip(L("When enabled, spawned/imported NPCs, ragdolls, and matching PMs will save and use all jigglebones disabled."))
    panel:AddItem(noJiggle)

    local relationLabel = vgui.Create("DLabel")
    relationLabel:SetText(L("NPC relationship"))
    relationLabel:SetTextColor(UI.Colors.Muted)
    relationLabel:SizeToContents()
    panel:AddItem(relationLabel)

    local relation = vgui.Create("DComboBox")
    relation:SetTall(22)
    relation:AddChoice(L("Friendly"), "friendly", true)
    relation:AddChoice(L("Hostile"), "hostile")
    relation:AddChoice(L("Neutral"), "neutral")
    relation.OnSelect = function(_, _, _, data)
        RunConsoleCommand("dynamic_model_importer_relation", tostring(data or "friendly"))
    end
    panel:AddItem(relation)

    panel:NumSlider(L("NPC health"), "dynamic_model_importer_health", 1, 9999, 0)

    local weaponLabel = vgui.Create("DLabel")
    weaponLabel:SetText(L("NPC weapon"))
    weaponLabel:SetTextColor(UI.Colors.Muted)
    weaponLabel:SizeToContents()
    panel:AddItem(weaponLabel)

    local weapon = vgui.Create("DComboBox")
    weapon:SetTall(22)
    weapon:SetValue(convar_string("dynamic_model_importer_weapon", "weapon_smg1"))
    weapon:AddChoice("SMG1", "weapon_smg1", true)
    weapon:AddChoice("AR2", "weapon_ar2")
    weapon:AddChoice(L("Shotgun"), "weapon_shotgun")
    weapon:AddChoice(L("Pistol"), "weapon_pistol")
    weapon:AddChoice(L("None"), "none")
    weapon.OnSelect = function(_, _, _, data)
        RunConsoleCommand("dynamic_model_importer_weapon", tostring(data or ""))
    end
    panel:AddItem(weapon)

    local customWeapon = vgui.Create("DTextEntry")
    customWeapon:SetTall(22)
    customWeapon:SetPlaceholderText(L("Custom weapon class, for example weapon_smg1"))
    customWeapon.OnEnter = function(self)
        RunConsoleCommand("dynamic_model_importer_weapon", self:GetText())
        weapon:SetValue(self:GetText())
    end
    panel:AddItem(customWeapon)

    UI.AddSection(panel, "4. Mouse Actions", "Left-click world: spawn NPC. Right-click world: spawn ragdoll.", UI.Colors.Purple)
    local help = vgui.Create("DLabel")
    help:SetWrap(true)
    help:SetAutoStretchVertical(true)
    help:SetText(L("Spawning only happens from the tool itself: left-click the world for NPC, right-click the world for ragdoll."))
    help:SetTextColor(UI.Colors.Text)
    panel:AddItem(help)

    search.OnChange = function()
        manifestList:Populate(DynamicModelImporter.LastModelList or {})
        legacyList:Populate(DynamicModelImporter.LastModelList or {})
    end

    local hookID = "DynamicModelImporterPanel_" .. tostring(panel)
    hook.Add("DynamicModelImporterListUpdated", hookID, function(entries)
        if IsValid(manifestList) then
            manifestList:Populate(entries)
        end
        if IsValid(legacyList) then
            legacyList:Populate(entries)
        end
    end)
    panel.OnRemove = function()
        hook.Remove("DynamicModelImporterListUpdated", hookID)
    end

    timer.Simple(0, function()
        if not IsValid(manifestList) or not IsValid(legacyList) then return end
        set_combo_value(relation, convar_string("dynamic_model_importer_relation", "friendly"))
        manifestList:Populate(DynamicModelImporter.LastModelList or {})
        legacyList:Populate(DynamicModelImporter.LastModelList or {})
        request_refresh()
    end)
end
