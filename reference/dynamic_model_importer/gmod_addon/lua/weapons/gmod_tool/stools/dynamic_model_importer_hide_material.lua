if SERVER then
    AddCSLuaFile()
    AddCSLuaFile("dynamic_model_importer/sh_core.lua")
end

include("dynamic_model_importer/sh_core.lua")

TOOL.Category = "#dynamic_model_importer.category"
TOOL.Name = "#tool.dynamic_model_importer_hide_material.name"
TOOL.Command = nil
TOOL.ConfigName = ""

TOOL.ClientConVar = {
    model_path = "",
    index = "0",
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

local request_override
local save_override

if CLIENT then
    language.Add("dynamic_model_importer.category", L("Model Importer"))
    language.Add("tool.dynamic_model_importer_hide_material.name", L("Hide Material Tool for Imported model"))
    language.Add("tool.dynamic_model_importer_hide_material.desc", L("Hide materials for any model path using the Dynamic Model Importer invisible material."))
    language.Add("tool.dynamic_model_importer_hide_material.0", L("Right-click an NPC, ragdoll, or player to select its model. Left-click toggles the selected material."))
end

if CLIENT then
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
        RunConsoleCommand("dynamic_model_importer_hide_material_model_path", modelPath)
        request_override(modelPath)
        hook.Run("DynamicModelImporterHideMaterialTargetSelected", modelPath)
        notification.AddLegacy(DynamicModelImporter.LF("Selected model: %s", modelPath), NOTIFY_GENERIC, 2)
        return true
    end

    function TOOL:LeftClick(trace)
        return true
    end

    function TOOL:RightClick(trace)
        local modelPath = DynamicModelImporter.EntityModelPath(get_target(trace, LocalPlayer()))
        if modelPath then select_model_path(modelPath) end
        return true
    end
else
    local function selected_material_index(tool)
        return math.max(0, math.floor(tool:GetClientNumber("index", 0) or 0))
    end

    local function send_override_to_player(ply, modelPath)
        if not IsValid(ply) then return end
        modelPath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
        if not modelPath then return end
        net.Start("dynamic_model_importer_send_override")
            net.WriteString(modelPath)
            net.WriteString(util.TableToJSON(DynamicModelImporter.GetModelPathOverride(modelPath), false) or "{}")
        net.Send(ply)
    end

    function TOOL:LeftClick(trace)
        local ply = self:GetOwner()
        local ent = get_target(trace, self:GetOwner())
        local modelPath = DynamicModelImporter.EntityModelPath(ent)
        if not modelPath or not IsValid(ent) or not ent.GetMaterials then
            DynamicModelImporter.Chat(ply, "Target has no valid model path.")
            return false
        end
        if not DynamicModelImporter.CanEditOverrides(ply) then
            DynamicModelImporter.Chat(ply, "Only admins can save Dynamic Model Importer repairs on this server.")
            return false
        end
        local mats = ent:GetMaterials() or {}
        local index = selected_material_index(self)
        if index < 0 or index >= #mats then
            DynamicModelImporter.Chat(ply, "No material selected.")
            return false
        end
        local override = DynamicModelImporter.GetModelPathOverride(modelPath)
        local key = tostring(index)
        if override.hidden_submaterials[key] then
            override.hidden_submaterials[key] = nil
        else
            override.hidden_submaterials[key] = DynamicModelImporter.InvisibleMaterialPath
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
        DynamicModelImporter.SendToolModelSelection(self:GetOwner(), "hide_material", modelPath)
        return true
    end
end

function TOOL:Reload(trace)
    return false
end

if CLIENT then
    TOOL.AimEnt = nil
    TOOL.HudData = { Mats = {}, CurMats = {}, OvrMats = {} }

    local function selected_material_index()
        local index = tonumber(read_convar_string("dynamic_model_importer_hide_material_index", "0")) or 0
        return math.max(0, math.floor(index))
    end

    function TOOL:Scroll(dir)
        if not IsValid(self.AimEnt) or not self.AimEnt.GetMaterials then return end
        local mats = self.AimEnt:GetMaterials() or {}
        if #mats == 0 then return end
        local index = selected_material_index()
        index = (index + dir) % #mats
        RunConsoleCommand("dynamic_model_importer_hide_material_index", tostring(index))
        surface.PlaySound("common/talk.wav")
    end

    hook.Add("PlayerBindPress", "DynamicModelImporterHideMaterialScroll", function(ply, bind, pressed)
        if not pressed or not IsValid(ply) then return end
        local wep = ply:GetActiveWeapon()
        if not IsValid(wep) or wep:GetClass() ~= "gmod_tool" then return end
        local tool = wep:GetToolObject()
        if not tool or tool.Mode ~= "dynamic_model_importer_hide_material" then return end
        if bind == "invnext" then
            tool:Scroll(1)
            return true
        elseif bind == "invprev" then
            tool:Scroll(-1)
            return true
        end
    end)

    local cachedPreviewMaterials = {}
    local previewMaterialSerial = 0

    local function preview_material_name(materialPath)
        materialPath = tostring(materialPath or "")
        if materialPath == "" then return nil end
        return string.gsub(materialPath, "\\", "/")
    end

    local function get_cached_preview_material(materialPath)
        local name = preview_material_name(materialPath)
        if not name then return nil end
        if not cachedPreviewMaterials[name] then
            local mat = Material(name)
            if not mat then return nil end
            local shader = tostring(mat:GetShader() or "")
            local baseTexture = mat.GetString and tostring(mat:GetString("$basetexture") or "") or ""
            if not mat:IsError() and baseTexture ~= "" and (string.find(shader, "VertexLitGeneric", 1, true) or string.find(shader, "Cable", 1, true)) then
                local safeName = string.sub(string.gsub(string.lower(name), "[^%w_]", "_"), 1, 96)
                previewMaterialSerial = previewMaterialSerial + 1
                cachedPreviewMaterials[name] = CreateMaterial("dmi_mat_preview_" .. safeName .. "_" .. previewMaterialSerial, "UnlitGeneric", {
                    ["$basetexture"] = baseTexture,
                    ["$vertexcolor"] = 1,
                    ["$vertexalpha"] = 1,
                })
            else
                cachedPreviewMaterials[name] = mat
            end
        end
        return cachedPreviewMaterials[name]
    end

    local function draw_clipped_text(text, font, x, y, color, maxWidth)
        text = tostring(text or "")
        surface.SetFont(font)
        local width = surface.GetTextSize(text)
        if width <= maxWidth then
            draw.SimpleText(text, font, x, y, color)
            return
        end
        while #text > 4 do
            text = string.sub(text, 1, #text - 1)
            width = surface.GetTextSize(text .. "...")
            if width <= maxWidth then break end
        end
        draw.SimpleText(text .. "...", font, x, y, color)
    end

    local function draw_material_preview_box(label, materialPath, x, y, iconSize, textWidth)
        draw.SimpleText(L(label), "DermaDefaultBold", x + iconSize + 10, y + 2, Color(255, 220, 150))
        draw_clipped_text(materialPath or "", "DermaDefault", x + iconSize + 10, y + 20, color_white, textWidth)
        surface.SetDrawColor(255, 255, 255, 220)
        surface.DrawOutlinedRect(x, y, iconSize, iconSize)
        local mat = get_cached_preview_material(materialPath)
        if mat and not mat:IsError() then
            surface.SetDrawColor(255, 255, 255, 255)
            surface.SetMaterial(mat)
            surface.DrawTexturedRect(x + 1, y + 1, iconSize - 2, iconSize - 2)
        else
            draw.RoundedBox(0, x + 1, y + 1, iconSize - 2, iconSize - 2, Color(55, 55, 55))
            draw.SimpleText("?", "DermaLarge", x + iconSize / 2, y + iconSize / 2, Color(255, 120, 120), TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
        end
    end

    function TOOL:Think()
        local ent = get_target(LocalPlayer():GetEyeTraceNoCursor(), LocalPlayer())
        if self.AimEnt ~= ent then
            self.AimEnt = ent
            if IsValid(ent) and ent.GetMaterials then
                self.HudData.Mats = ent:GetMaterials() or {}
            else
                self.HudData.Mats = {}
            end
        end
        self.HudData.CurMats = table.Copy(self.HudData.Mats or {})
        self.HudData.OvrMats = {}
        if IsValid(self.AimEnt) and self.AimEnt.GetSubMaterial then
            for i = 0, #(self.HudData.Mats or {}) - 1 do
                local override = self.AimEnt:GetSubMaterial(i)
                if override and override ~= "" then
                    self.HudData.OvrMats[i] = override
                    self.HudData.CurMats[i + 1] = override
                end
            end
        end
    end

    function TOOL:DrawHUD()
        if not IsValid(self.AimEnt) or not self.HudData.Mats or #self.HudData.Mats == 0 then return end
        local selectedIndex = selected_material_index()
        if selectedIndex >= #self.HudData.Mats then
            selectedIndex = #self.HudData.Mats - 1
        end
        selectedIndex = math.max(0, selectedIndex)
        local rowHeight = 18
        local materialCount = #self.HudData.Mats
        local maxRows = math.max(8, math.floor((ScrH() - 32) / rowHeight) - 2)
        local rows = math.min(materialCount, maxRows)
        local panelHeight = rowHeight * (rows + 2) + 8
        local width = math.min(560, math.max(380, math.floor(ScrW() * 0.34)))
        local x = math.max(12, math.floor(ScrW() / 2 - width - 180))
        local y = math.Clamp(math.floor(ScrH() / 2 - panelHeight / 2), 12, math.max(12, ScrH() - panelHeight - 12))
        local startIndex = math.Clamp(selectedIndex - math.floor(rows / 2), 0, math.max(0, materialCount - rows))
        local endIndex = math.min(materialCount - 1, startIndex + rows - 1)
        draw.RoundedBox(4, x, y, width, panelHeight, Color(0, 0, 0, 180))
        draw.SimpleText(L("Materials"), "ChatFont", x + 6, y + 5, color_white)
        draw.SimpleText(string.format("%d-%d / %d", startIndex, endIndex, materialCount), "ChatFont", x + width - 8, y + 5, Color(210, 210, 210), TEXT_ALIGN_RIGHT)
        for i = 1, rows do
            local index = startIndex + i - 1
            local rowY = y + 5 + rowHeight * i
            if index == selectedIndex then
                draw.RoundedBox(0, x + 3, rowY - 1, width - 6, rowHeight, Color(0, 150, 255, 110))
            end
            local materialPath = tostring(self.HudData.CurMats[index + 1] or "")
            local color = self.HudData.OvrMats[index] and Color(255, 120, 120) or color_white
            draw_clipped_text(index .. ": " .. materialPath, "ChatFont", x + 6, rowY, color, width - 12)
        end
        if startIndex > 0 then
            draw.SimpleText("...", "ChatFont", x + width - 28, y + rowHeight + 3, Color(210, 210, 210), TEXT_ALIGN_RIGHT)
        end
        if endIndex < materialCount - 1 then
            draw.SimpleText("...", "ChatFont", x + width - 28, y + 5 + rowHeight * rows, Color(210, 210, 210), TEXT_ALIGN_RIGHT)
        end

        local originalPath = tostring(self.HudData.Mats[selectedIndex + 1] or "")
        local currentPath = tostring(self.HudData.CurMats[selectedIndex + 1] or originalPath)
        local previewX = x + width + 16
        local previewY = y
        local previewW = 360
        local iconSize = 54
        local gap = 10
        local previewH = 34 + (iconSize + gap) * 3
        if previewX + previewW > ScrW() - 12 then
            previewX = math.max(12, x - previewW - 16)
        end

        draw.RoundedBox(4, previewX, previewY, previewW, previewH, Color(0, 0, 0, 180))
        draw.SimpleText(L("Selected material preview"), "ChatFont", previewX + 8, previewY + 7, color_white)
        draw.SimpleText(L("Index") .. ": " .. tostring(selectedIndex), "ChatFont", previewX + 220, previewY + 7, Color(220, 220, 220))

        local textWidth = previewW - iconSize - 28
        local rowY = previewY + 30
        draw_material_preview_box("Tool Material:", DynamicModelImporter.InvisibleMaterialPath, previewX + 8, rowY, iconSize, textWidth)
        rowY = rowY + iconSize + gap
        draw_material_preview_box("Original Material:", originalPath, previewX + 8, rowY, iconSize, textWidth)
        rowY = rowY + iconSize + gap
        draw_material_preview_box("Current Material:", currentPath, previewX + 8, rowY, iconSize, textWidth)
    end

    function TOOL.BuildCPanel(panel)
        local UI = DynamicModelImporter.UI
        panel:AddControl("Header", {
            Description = L("Right-click an NPC, ragdoll, or player to select its model. Left-click toggles the selected material.")
        })

        UI.AddSection(panel, "1. Select Target", "Right-click an NPC, ragdoll, or player. Saved material overrides apply to every entity using that model path.", UI.Colors.Green)

        local state = {
            model_path = DynamicModelImporter.NormalizeOverrideModelPath(read_convar_string("dynamic_model_importer_hide_material_model_path", "")),
            preview = nil,
            materials = {},
            override = DynamicModelImporter.EmptyModelOverride(),
        }

        local status = vgui.Create("DLabel")
        status:SetWrap(true)
        status:SetAutoStretchVertical(true)
        status:SetTextColor(UI.Colors.Muted)
        panel:AddItem(status)

        local selected = panel:TextEntry(L("Selected model path"), "dynamic_model_importer_hide_material_model_path")
        selected:SetEditable(false)

        UI.AddSection(panel, "2. Choose Material", "Use the table, selected index, or mouse wheel while aiming at a model. Hidden materials are marked in red.", UI.Colors.Blue)

        panel:NumSlider(L("Selected material index"), "dynamic_model_importer_hide_material_index", 0, 255, 0)

        local materialList = vgui.Create("DListView")
        materialList:SetTall(220)
        materialList:SetMultiSelect(false)
        materialList:AddColumn(L("Index"))
        materialList:AddColumn(L("Material"))
        materialList:AddColumn(L("Hidden"))
        panel:AddItem(UI.StyleList(materialList))

        local previewPanel = vgui.Create("DPanel")
        previewPanel:SetTall(154)
        panel:AddItem(previewPanel)

        local function set_status(text)
            if IsValid(status) then status:SetText(L(text or "")) end
        end

        local function cleanup_preview()
            if IsValid(state.preview) then state.preview:Remove() end
            state.preview = nil
        end

        local function material_hidden(index)
            return state.override.hidden_submaterials[tostring(index)] ~= nil
        end

        local current_index
        local populatingMaterials = false
        state.selected_index = selected_material_index()

        local function set_current_index(index)
            index = math.max(0, math.floor(tonumber(index) or 0))
            state.selected_index = index
            RunConsoleCommand("dynamic_model_importer_hide_material_index", tostring(index))
            return index
        end

        local function populate_materials(preferredIndex)
            local selectedIndex = tonumber(preferredIndex) or state.selected_index or selected_material_index()
            if #state.materials > 0 then
                selectedIndex = math.Clamp(selectedIndex, 0, #state.materials - 1)
            end
            state.selected_index = selectedIndex
            local selectedLine = nil
            populatingMaterials = true
            materialList:Clear()
            for _, materialInfo in ipairs(state.materials) do
                local hidden = material_hidden(materialInfo.index)
                local line = materialList:AddLine(tostring(materialInfo.index), materialInfo.path, hidden and L("yes") or L("no"))
                line.SubMaterialIndex = materialInfo.index
                if hidden then
                    for _, column in pairs(line.Columns or {}) do
                        if IsValid(column) and column.SetTextColor then
                            column:SetTextColor(UI.Colors.Red)
                        end
                    end
                end
                if materialInfo.index == selectedIndex then
                    selectedLine = line
                end
            end
            if IsValid(selectedLine) then
                materialList:SelectItem(selectedLine)
            end
            populatingMaterials = false
            set_current_index(selectedIndex)
        end

        function previewPanel:Paint(width, height)
            draw.RoundedBox(5, 0, 0, width, height, UI.Colors.PanelSoft)
            surface.SetDrawColor(UI.Colors.Border)
            surface.DrawOutlinedRect(0, 0, width, height)
            draw.SimpleText(L("Selected material preview"), "DermaDefaultBold", 8, 7, UI.Colors.Blue)
            local index = current_index and current_index() or selected_material_index()
            local materialInfo = state.materials[index + 1]
            if not materialInfo then
                draw.SimpleText(L("No material selected."), "DermaDefault", 8, 30, UI.Colors.Muted)
                return
            end

            local originalPath = tostring(materialInfo.path or "")
            local currentPath = material_hidden(index) and DynamicModelImporter.InvisibleMaterialPath or originalPath
            draw_clipped_text(tostring(index) .. ": " .. originalPath, "DermaDefault", 8, 28, UI.Colors.Muted, math.max(width - 16, 60))

            local iconSize = 54
            local firstY = 50
            local secondX = math.max(8, math.floor(width / 2))
            local textWidth = math.max(secondX - iconSize - 22, 60)
            draw_material_preview_box("Original Material:", originalPath, 8, firstY, iconSize, textWidth)
            draw_material_preview_box("Current Material:", currentPath, secondX, firstY, iconSize, math.max(width - secondX - iconSize - 18, 60))
        end

        UI.AddSection(panel, "3. Material Actions", "Hide applies the invisible material. Restore removes the saved override for the selected model path.", UI.Colors.Orange)

        local hideButton = panel:Button(L("Hide current material"))
        local restoreButton = panel:Button(L("Restore current material"))
        local restoreAllButton = panel:Button(L("Restore all materials"))
        UI.StyleButton(hideButton, UI.Colors.Orange)
        UI.StyleButton(restoreButton, UI.Colors.Green)
        UI.StyleButton(restoreAllButton, UI.Colors.Blue)

        local function inspect_model()
            cleanup_preview()
            state.materials = {}
            if not state.model_path then
                set_status("Select a model by right-clicking an NPC, ragdoll, or player.")
                populate_materials()
                return
            end
            local model = ClientsideModel(state.model_path, RENDERGROUP_OTHER)
            if not IsValid(model) then
                set_status(string.format(L("Could not inspect model: %s"), state.model_path))
                populate_materials()
                return
            end
            model:SetNoDraw(true)
            state.preview = model
            for index, materialPath in ipairs(model:GetMaterials() or {}) do
                state.materials[#state.materials + 1] = { index = index - 1, path = tostring(materialPath or "") }
            end
            populate_materials()
            set_status("Loaded repair settings.")
        end

        local function load_model_path(modelPath)
            modelPath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
            if not modelPath then return end
            state.model_path = modelPath
            state.override = copy_model_override((DynamicModelImporter.LastModelOverrides or {})[modelPath])
            RunConsoleCommand("dynamic_model_importer_hide_material_model_path", modelPath)
            request_override(modelPath)
            inspect_model()
        end

        local function save_current(preferredIndex)
            if not state.model_path then
                set_status("Select a model by right-clicking an NPC, ragdoll, or player.")
                return
            end
            state.override = DynamicModelImporter.SanitizeModelOverride(state.override)
            save_override(state.model_path, state.override)
            populate_materials(preferredIndex or current_index())
        end

        materialList.OnRowSelected = function(_, _, line)
            if populatingMaterials then return end
            if IsValid(line) and line.SubMaterialIndex ~= nil then
                set_current_index(line.SubMaterialIndex)
            end
        end

        current_index = function()
            local line = selected_list_line(materialList)
            if line and line.SubMaterialIndex ~= nil then
                state.selected_index = line.SubMaterialIndex
                return line.SubMaterialIndex
            end
            return state.selected_index or selected_material_index()
        end

        hideButton.DoClick = function()
            local index = set_current_index(current_index())
            state.override.hidden_submaterials[tostring(index)] = DynamicModelImporter.InvisibleMaterialPath
            save_current(index)
        end

        restoreButton.DoClick = function()
            local index = set_current_index(current_index())
            state.override.hidden_submaterials[tostring(index)] = nil
            save_current(index)
        end

        restoreAllButton.DoClick = function()
            local index = set_current_index(current_index())
            state.override.hidden_submaterials = {}
            save_current(index)
        end

        local targetHookID = "DynamicModelImporterHideMaterialTarget_" .. tostring(panel)
        hook.Add("DynamicModelImporterHideMaterialTargetSelected", targetHookID, load_model_path)

        local overrideHookID = "DynamicModelImporterHideMaterialOverride_" .. tostring(panel)
        hook.Add("DynamicModelImporterOverrideUpdated", overrideHookID, function(modelPath, override)
            if DynamicModelImporter.NormalizeOverrideModelPath(modelPath) ~= state.model_path then return end
            state.override = copy_model_override(override)
            populate_materials(selected_material_index())
            set_status("Loaded repair settings.")
        end)

        panel.OnRemove = function()
            cleanup_preview()
            hook.Remove("DynamicModelImporterHideMaterialTargetSelected", targetHookID)
            hook.Remove("DynamicModelImporterOverrideUpdated", overrideHookID)
        end

        timer.Simple(0, function()
            if IsValid(panel) and state.model_path then
                load_model_path(state.model_path)
            else
                set_status("Select a model by right-clicking an NPC, ragdoll, or player.")
            end
        end)
    end
end
