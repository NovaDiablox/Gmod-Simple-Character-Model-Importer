DynamicModelImporter = DynamicModelImporter or {}
DynamicModelImporter.StaticRoot = "data_static/dynamic_model_importer/models"
DynamicModelImporter.LegacyAutorunPattern = "lua/autorun/*_sheepylord.lua"
DynamicModelImporter.OverrideDataPath = "dynamic_model_importer/model_overrides.json"
DynamicModelImporter.InvisibleMaterialPath = "dynamic_model_importer/invisible"
DynamicModelImporter.Translations = {
    ["zh-CN"] = {
        ["Model Importer"] = "模型导入器",
        ["Dynamic Model Importer"] = "动态模型导入器",
        ["Spawn MMD Character Importer models."] = "生成 MMD Character Importer 模型。",
        ["Select a model in the menu. Left-click the world to spawn an NPC; right-click the world to spawn a ragdoll."] = "在菜单中选择模型。左键点击世界生成 NPC；右键点击世界生成布娃娃。",
        ["Shows models produced by MMD Character Importer. Select a row, then left-click the world to spawn an NPC or right-click the world to spawn a ragdoll."] = "显示由 MMD Character Importer 生成的模型。选择一行后，左键点击世界生成 NPC，或右键点击世界生成布娃娃。",
        ["Refresh model list"] = "刷新模型列表",
        ["Search models..."] = "搜索模型...",
        ["Friendly"] = "友好",
        ["Hostile"] = "敌对",
        ["Neutral"] = "中立",
        ["NPC health"] = "NPC 生命值",
        ["Shotgun"] = "霰弹枪",
        ["Pistol"] = "手枪",
        ["None"] = "无",
        ["Custom weapon class, for example weapon_smg1"] = "自定义武器类，例如 weapon_smg1",
        ["Manifest imported models"] = "清单导入模型",
        ["Legacy autorun models"] = "旧版 autorun 模型",
        ["Model"] = "模型",
        ["Category"] = "分类",
        ["Model path"] = "模型路径",
        ["PM"] = "玩家模型",
        ["yes"] = "是",
        ["no"] = "否",
        ["Selected model id"] = "已选模型 ID",
        ["Spawning only happens from the tool itself: left-click the world for NPC, right-click the world for ragdoll."] = "只能通过此工具生成：左键点击世界生成 NPC，右键点击世界生成布娃娃。",
        ["Model is not available: %s"] = "模型不可用：%s",
        ["Failed to create NPC class: %s"] = "创建 NPC 类失败：%s",
        ["Spawned NPC: %s"] = "已生成 NPC：%s",
        ["Failed to create ragdoll."] = "创建布娃娃失败。",
        ["Spawned ragdoll: %s"] = "已生成布娃娃：%s",
        ["Could not load model manifest."] = "无法加载模型清单。",
        ["Invalid model id."] = "模型 ID 无效。",
        ["Dynamic Model Repair"] = "动态模型修复",
        ["Repair imported model materials and jiggle bones."] = "修复导入模型的材质和摇摆骨骼。",
        ["Select a model in the menu. Save repairs, then spawned NPCs, ragdolls, and matching player models use them automatically."] = "在菜单中选择模型。保存修复后，生成的 NPC、布娃娃和匹配的玩家模型会自动使用这些设置。",
        ["Hide bad materials and disable jiggle bones for Dynamic Model Importer models. Settings are saved server-wide."] = "隐藏有问题的材质，并禁用 Dynamic Model Importer 模型的摇摆骨骼。设置会保存到服务器。",
        ["Materials"] = "材质",
        ["Index"] = "索引",
        ["Material"] = "材质",
        ["Hidden"] = "已隐藏",
        ["Hide selected material"] = "隐藏所选材质",
        ["Restore selected material"] = "还原所选材质",
        ["Restore all materials"] = "还原所有材质",
        ["Bones"] = "骨骼",
        ["Bone"] = "骨骼",
        ["Parent"] = "父骨骼",
        ["Children"] = "子骨骼",
        ["No jiggle"] = "无摇摆",
        ["Essential"] = "关键骨骼",
        ["locked"] = "已锁定",
        ["Disable selected bone jiggle"] = "禁用所选骨骼摇摆",
        ["Restore selected bone jiggle"] = "还原所选骨骼摇摆",
        ["Disable all jiggle"] = "禁用所有摇摆",
        ["Restore all jiggle"] = "还原所有摇摆",
        ["1. Select Target"] = "1. 选择目标",
        ["Right-click an NPC, ragdoll, or player. Saved jigglebone overrides apply to every entity using that model path."] = "右键点击 NPC、布娃娃或玩家。保存的摇摆骨骼覆盖设置会应用到所有使用该模型路径的实体。",
        ["2. Filter Bones"] = "2. 筛选骨骼",
        ["Filter by bone name keywords and/or a parent/root bone. Subset actions use the currently visible filtered rows."] = "按骨骼名称关键词和/或父级/根骨骼筛选。子集操作会作用于当前可见的筛选行。",
        ["Filters decide which bones are shown in the table. Table actions affect every row currently shown."] = "筛选器决定表格中显示哪些骨骼。表格操作会作用于当前显示的每一行。",
        ["Keyword filter"] = "关键词筛选",
        ["Parent/root filter"] = "父级/根骨骼筛选",
        ["Include descendants"] = "包含子级",
        ["Hair"] = "头发",
        ["Sleeves"] = "袖子",
        ["Skirt"] = "裙子",
        ["Left side"] = "左侧",
        ["Right side"] = "右侧",
        ["Clear filter"] = "清除筛选",
        ["3. Bone Table"] = "3. 骨骼表",
        ["Disabled jigglebones are marked in red. Left-click in the world toggles all jigglebones for the selected model."] = "禁用的摇摆骨骼会以红色标记。左键点击世界会切换所选模型的所有摇摆骨骼。",
        ["Disabled jigglebones are marked in red. Locked essential skeleton bones cannot be restored to jiggle."] = "禁用的摇摆骨骼会以红色标记。锁定的关键骨骼不能还原为摇摆骨骼。",
        ["4. Jigglebone Actions"] = "4. 摇摆骨骼操作",
        ["Use selected-bone actions for precise fixes, filtered actions for subsets, or bulk actions when the model should have no jiggle at all."] = "使用所选骨骼操作进行精确修复，使用筛选操作处理子集，或在模型应完全无摇摆时使用批量操作。",
        ["Use selected-bone actions for precise fixes, table actions for every row currently shown, or bulk actions when the model should have no jiggle at all. Essential skeleton bones stay locked to no-jiggle."] = "使用所选骨骼操作进行精确修复，使用表格操作处理当前显示的所有行，或在模型应完全无摇摆时使用批量操作。关键骨骼会保持锁定为无摇摆。",
        ["Disable filtered bones"] = "禁用筛选骨骼",
        ["Restore filtered bones"] = "还原筛选骨骼",
        ["Disable all bones in table"] = "禁用表格中的所有骨骼",
        ["Restore all bones in table"] = "还原表格中的所有骨骼",
        ["No active filter. Use Disable all jiggle or Restore all jiggle for whole-model changes."] = "没有启用筛选。若要修改整个模型，请使用“禁用所有摇摆”或“还原所有摇摆”。",
        ["No filtered bones matched."] = "没有匹配的筛选骨骼。",
        ["No bones in table."] = "表格中没有骨骼。",
        ["%d filtered bone(s)."] = "%d 个筛选骨骼。",
        ["%d bone(s) in table."] = "表格中有 %d 个骨骼。",
        ["%d table bone(s)."] = "已处理 %d 个表格骨骼。",
        ["Saved repair settings apply to NPCs, ragdolls, and matching player models."] = "保存的修复设置会应用到 NPC、布娃娃和匹配的玩家模型。",
        ["Select a model first."] = "请先选择模型。",
        ["Selected model has no inspectable model path."] = "所选模型没有可检查的模型路径。",
        ["Could not inspect model: %s"] = "无法检查模型：%s",
        ["Loaded repair settings."] = "已加载修复设置。",
        ["No material selected."] = "未选择材质。",
        ["No bone selected."] = "未选择骨骼。",
        ["Target does not match the selected imported model."] = "目标与所选导入模型不匹配。",
        ["Applied saved repairs to target."] = "已将保存的修复应用到目标。",
        ["Only admins can save Dynamic Model Importer repairs on this server."] = "只有管理员可以在此服务器上保存 Dynamic Model Importer 修复。",
        ["Saved repairs for: %s"] = "已保存修复：%s",
        ["Hide Material Tool for Imported model"] = "导入模型隐藏材质工具",
        ["Hide materials for any model path using the Dynamic Model Importer invisible material."] = "使用 Dynamic Model Importer 的隐形材质隐藏任意模型路径的材质。",
        ["Left-click an NPC, ragdoll, or player to select its model."] = "左键点击 NPC、布娃娃或玩家以选择其模型。",
        ["Right-click an NPC, ragdoll, or player to select its model. Left-click toggles the selected material."] = "右键点击 NPC、布娃娃或玩家以选择其模型。左键切换所选材质的隐藏状态。",
        ["Right-click an NPC, ragdoll, or player to select its model. Left-click toggles all jigglebones."] = "右键点击 NPC、布娃娃或玩家以选择其模型。左键切换所有摇摆骨骼。",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles the selected material."] = "右键点击 NPC、布娃娃、玩家、物品、武器或视图模型以选择其模型。左键切换所选材质的隐藏状态。",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles all jigglebones."] = "右键点击 NPC、布娃娃、玩家、物品、武器或视图模型以选择其模型。左键切换所有摇摆骨骼。",
        ["Target has no valid model path."] = "目标没有有效的模型路径。",
        ["Selected model: %s"] = "已选择模型：%s",
        ["Selected model: %s (%s)"] = "已选择模型：%s（%s）",
        ["Importer model scope"] = "导入模型范围",
        ["Exact model path scope"] = "精确模型路径范围",
        ["Importer model scope: saved repairs use the importer model path and continue to work for spawned NPCs, ragdolls, and matching player models."] = "导入模型范围：保存的修复会使用导入器模型路径，并继续适用于生成的 NPC、布娃娃和匹配的玩家模型。",
        ["Exact model path scope: saved repairs affect only entities using this exact .mdl path, including matching viewmodels or weapons."] = "精确模型路径范围：保存的修复只影响使用此精确 .mdl 路径的实体，包括匹配的视图模型或武器。",
        ["Selected material index"] = "所选材质索引",
        ["Hide current material"] = "隐藏当前材质",
        ["Restore current material"] = "还原当前材质",
        ["Selected material preview"] = "所选材质预览",
        ["Tool Material:"] = "工具材质：",
        ["Original Material:"] = "原始材质：",
        ["Current Material:"] = "当前材质：",
        ["Select an NPC, ragdoll, or player. Saved material hides apply to every entity using the same model path."] = "选择 NPC、布娃娃或玩家。保存的隐藏材质会应用到所有使用相同模型路径的实体。",
        ["Selected model path"] = "所选模型路径",
        ["Select a model by left-clicking an NPC, ragdoll, or player."] = "左键点击 NPC、布娃娃或玩家来选择模型。",
        ["Select a model by right-clicking an NPC, ragdoll, or player."] = "右键点击 NPC、布娃娃或玩家来选择模型。",
        ["Select a model by right-clicking an NPC, ragdoll, player, prop, weapon, or viewmodel."] = "右键点击 NPC、布娃娃、玩家、物品、武器或视图模型来选择模型。",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel. SheepyLord/imported models use importer scope; other targets use exact .mdl path scope."] = "右键点击 NPC、布娃娃、玩家、物品、武器或视图模型。SheepyLord/导入模型使用导入模型范围；其他目标使用精确 .mdl 路径范围。",
        ["Jigglebone tool for Imported model"] = "导入模型摇摆骨骼工具",
        ["Disable jigglebones for any model path."] = "禁用任意模型路径的摇摆骨骼。",
        ["Select an NPC, ragdoll, or player. Saved jigglebone settings apply to every entity using the same model path."] = "选择 NPC、布娃娃或玩家。保存的摇摆骨骼设置会应用到所有使用相同模型路径的实体。",
        ["Invalid model path."] = "模型路径无效。",
        ["Saved repairs for model path: %s"] = "已保存模型路径修复：%s",
        ["Spawn model without jigglebone"] = "生成模型时禁用摇摆骨骼",
        ["When enabled, spawned/imported NPCs, ragdolls, and matching PMs will save and use all jigglebones disabled."] = "启用后，生成/导入的 NPC、布娃娃和匹配的玩家模型会保存并使用禁用所有摇摆骨骼的设置。",
    },
    ["fr"] = {
        ["Model Importer"] = "Importateur de modèles",
        ["Dynamic Model Importer"] = "Importateur dynamique de modèles",
        ["Spawn MMD Character Importer models."] = "Fait apparaître les modèles de MMD Character Importer.",
        ["Select a model in the menu. Left-click the world to spawn an NPC; right-click the world to spawn a ragdoll."] = "Sélectionnez un modèle dans le menu. Clic gauche dans le monde pour créer un PNJ ; clic droit pour créer un ragdoll.",
        ["Shows models produced by MMD Character Importer. Select a row, then left-click the world to spawn an NPC or right-click the world to spawn a ragdoll."] = "Affiche les modèles produits par MMD Character Importer. Sélectionnez une ligne, puis faites un clic gauche dans le monde pour créer un PNJ ou un clic droit pour créer un ragdoll.",
        ["Refresh model list"] = "Actualiser la liste des modèles",
        ["Search models..."] = "Rechercher des modèles...",
        ["Friendly"] = "Amical",
        ["Hostile"] = "Hostile",
        ["Neutral"] = "Neutre",
        ["NPC health"] = "Santé du PNJ",
        ["Shotgun"] = "Fusil à pompe",
        ["Pistol"] = "Pistolet",
        ["None"] = "Aucun",
        ["Custom weapon class, for example weapon_smg1"] = "Classe d'arme personnalisée, par exemple weapon_smg1",
        ["Manifest imported models"] = "Modèles importés par manifeste",
        ["Legacy autorun models"] = "Modèles autorun hérités",
        ["Model"] = "Modèle",
        ["Category"] = "Catégorie",
        ["Model path"] = "Chemin du modèle",
        ["PM"] = "Modèle joueur",
        ["yes"] = "oui",
        ["no"] = "non",
        ["Selected model id"] = "ID du modèle sélectionné",
        ["Spawning only happens from the tool itself: left-click the world for NPC, right-click the world for ragdoll."] = "L'apparition se fait uniquement avec l'outil : clic gauche dans le monde pour un PNJ, clic droit pour un ragdoll.",
        ["Model is not available: %s"] = "Le modèle n'est pas disponible : %s",
        ["Failed to create NPC class: %s"] = "Impossible de créer la classe de PNJ : %s",
        ["Spawned NPC: %s"] = "PNJ créé : %s",
        ["Failed to create ragdoll."] = "Impossible de créer le ragdoll.",
        ["Spawned ragdoll: %s"] = "Ragdoll créé : %s",
        ["Could not load model manifest."] = "Impossible de charger le manifeste du modèle.",
        ["Invalid model id."] = "ID de modèle invalide.",
        ["Dynamic Model Repair"] = "Réparation de modèles dynamiques",
        ["Repair imported model materials and jiggle bones."] = "Répare les matériaux et les os jiggle des modèles importés.",
        ["Select a model in the menu. Save repairs, then spawned NPCs, ragdolls, and matching player models use them automatically."] = "Sélectionnez un modèle dans le menu. Enregistrez les corrections ; les PNJ, ragdolls et modèles joueur correspondants les utiliseront automatiquement.",
        ["Hide bad materials and disable jiggle bones for Dynamic Model Importer models. Settings are saved server-wide."] = "Masque les matériaux incorrects et désactive les os jiggle des modèles Dynamic Model Importer. Les réglages sont enregistrés sur le serveur.",
        ["Materials"] = "Matériaux",
        ["Index"] = "Indice",
        ["Material"] = "Matériau",
        ["Hidden"] = "Masqué",
        ["Hide selected material"] = "Masquer le matériau sélectionné",
        ["Restore selected material"] = "Restaurer le matériau sélectionné",
        ["Restore all materials"] = "Restaurer tous les matériaux",
        ["Bones"] = "Os",
        ["Bone"] = "Os",
        ["Parent"] = "Parent",
        ["Children"] = "Enfants",
        ["No jiggle"] = "Sans jiggle",
        ["Essential"] = "Essentiel",
        ["locked"] = "verrouillé",
        ["Disable selected bone jiggle"] = "Désactiver le jiggle de l'os sélectionné",
        ["Restore selected bone jiggle"] = "Restaurer le jiggle de l'os sélectionné",
        ["Disable all jiggle"] = "Désactiver tout le jiggle",
        ["Restore all jiggle"] = "Restaurer tout le jiggle",
        ["1. Select Target"] = "1. Sélectionner la cible",
        ["Right-click an NPC, ragdoll, or player. Saved jigglebone overrides apply to every entity using that model path."] = "Clic droit sur un PNJ, un ragdoll ou un joueur. Les remplacements jigglebone enregistrés s'appliquent à toutes les entités utilisant ce chemin de modèle.",
        ["2. Filter Bones"] = "2. Filtrer les os",
        ["Filter by bone name keywords and/or a parent/root bone. Subset actions use the currently visible filtered rows."] = "Filtre par mots-clés de nom d'os et/ou par os parent/racine. Les actions de sous-ensemble utilisent les lignes filtrées visibles.",
        ["Filters decide which bones are shown in the table. Table actions affect every row currently shown."] = "Les filtres déterminent quels os sont affichés dans le tableau. Les actions du tableau affectent chaque ligne actuellement visible.",
        ["Keyword filter"] = "Filtre par mot-clé",
        ["Parent/root filter"] = "Filtre parent/racine",
        ["Include descendants"] = "Inclure les descendants",
        ["Hair"] = "Cheveux",
        ["Sleeves"] = "Manches",
        ["Skirt"] = "Jupe",
        ["Left side"] = "Côté gauche",
        ["Right side"] = "Côté droit",
        ["Clear filter"] = "Effacer le filtre",
        ["3. Bone Table"] = "3. Tableau des os",
        ["Disabled jigglebones are marked in red. Left-click in the world toggles all jigglebones for the selected model."] = "Les jigglebones désactivés sont marqués en rouge. Un clic gauche dans le monde bascule tous les jigglebones du modèle sélectionné.",
        ["Disabled jigglebones are marked in red. Locked essential skeleton bones cannot be restored to jiggle."] = "Les jigglebones désactivés sont marqués en rouge. Les os essentiels verrouillés ne peuvent pas être restaurés en jiggle.",
        ["4. Jigglebone Actions"] = "4. Actions jigglebone",
        ["Use selected-bone actions for precise fixes, filtered actions for subsets, or bulk actions when the model should have no jiggle at all."] = "Utilisez les actions sur les os sélectionnés pour les corrections précises, les actions filtrées pour les sous-ensembles, ou les actions globales si le modèle ne doit avoir aucun jiggle.",
        ["Use selected-bone actions for precise fixes, table actions for every row currently shown, or bulk actions when the model should have no jiggle at all. Essential skeleton bones stay locked to no-jiggle."] = "Utilisez les actions sur les os sélectionnés pour les corrections précises, les actions du tableau pour toutes les lignes visibles, ou les actions globales si le modèle ne doit avoir aucun jiggle. Les os essentiels restent verrouillés sans jiggle.",
        ["Disable filtered bones"] = "Désactiver les os filtrés",
        ["Restore filtered bones"] = "Restaurer les os filtrés",
        ["Disable all bones in table"] = "Désactiver tous les os du tableau",
        ["Restore all bones in table"] = "Restaurer tous les os du tableau",
        ["No active filter. Use Disable all jiggle or Restore all jiggle for whole-model changes."] = "Aucun filtre actif. Utilisez Désactiver tout le jiggle ou Restaurer tout le jiggle pour modifier tout le modèle.",
        ["No filtered bones matched."] = "Aucun os filtré ne correspond.",
        ["No bones in table."] = "Aucun os dans le tableau.",
        ["%d filtered bone(s)."] = "%d os filtré(s).",
        ["%d bone(s) in table."] = "%d os dans le tableau.",
        ["%d table bone(s)."] = "%d os du tableau.",
        ["Saved repair settings apply to NPCs, ragdolls, and matching player models."] = "Les réglages de réparation enregistrés s'appliquent aux PNJ, ragdolls et modèles joueur correspondants.",
        ["Select a model first."] = "Sélectionnez d'abord un modèle.",
        ["Selected model has no inspectable model path."] = "Le modèle sélectionné n'a pas de chemin inspectable.",
        ["Could not inspect model: %s"] = "Impossible d'inspecter le modèle : %s",
        ["Loaded repair settings."] = "Réglages de réparation chargés.",
        ["No material selected."] = "Aucun matériau sélectionné.",
        ["No bone selected."] = "Aucun os sélectionné.",
        ["Target does not match the selected imported model."] = "La cible ne correspond pas au modèle importé sélectionné.",
        ["Applied saved repairs to target."] = "Réparations enregistrées appliquées à la cible.",
        ["Only admins can save Dynamic Model Importer repairs on this server."] = "Seuls les admins peuvent enregistrer les réparations Dynamic Model Importer sur ce serveur.",
        ["Saved repairs for: %s"] = "Réparations enregistrées pour : %s",
        ["Hide Material Tool for Imported model"] = "Outil de masquage de matériau pour modèle importé",
        ["Hide materials for any model path using the Dynamic Model Importer invisible material."] = "Masque les matériaux de n'importe quel chemin de modèle avec le matériau invisible de Dynamic Model Importer.",
        ["Left-click an NPC, ragdoll, or player to select its model."] = "Clic gauche sur un PNJ, un ragdoll ou un joueur pour sélectionner son modèle.",
        ["Right-click an NPC, ragdoll, or player to select its model. Left-click toggles the selected material."] = "Clic droit sur un PNJ, un ragdoll ou un joueur pour sélectionner son modèle. Clic gauche bascule le matériau sélectionné.",
        ["Right-click an NPC, ragdoll, or player to select its model. Left-click toggles all jigglebones."] = "Clic droit sur un PNJ, un ragdoll ou un joueur pour sélectionner son modèle. Clic gauche bascule tous les jigglebones.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles the selected material."] = "Clic droit sur un PNJ, un ragdoll, un joueur, un prop, une arme ou un viewmodel pour sélectionner son modèle. Clic gauche bascule le matériau sélectionné.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles all jigglebones."] = "Clic droit sur un PNJ, un ragdoll, un joueur, un prop, une arme ou un viewmodel pour sélectionner son modèle. Clic gauche bascule tous les jigglebones.",
        ["Target has no valid model path."] = "La cible n'a pas de chemin de modèle valide.",
        ["Selected model: %s"] = "Modèle sélectionné : %s",
        ["Selected model: %s (%s)"] = "Modèle sélectionné : %s (%s)",
        ["Importer model scope"] = "Portée du modèle importé",
        ["Exact model path scope"] = "Portée du chemin exact du modèle",
        ["Importer model scope: saved repairs use the importer model path and continue to work for spawned NPCs, ragdolls, and matching player models."] = "Portée du modèle importé : les corrections enregistrées utilisent le chemin du modèle importé et continuent de fonctionner pour les PNJ, ragdolls et modèles joueur correspondants.",
        ["Exact model path scope: saved repairs affect only entities using this exact .mdl path, including matching viewmodels or weapons."] = "Portée du chemin exact : les corrections enregistrées n'affectent que les entités utilisant exactement ce chemin .mdl, y compris les viewmodels ou armes correspondants.",
        ["Selected material index"] = "Indice du matériau sélectionné",
        ["Hide current material"] = "Masquer le matériau actuel",
        ["Restore current material"] = "Restaurer le matériau actuel",
        ["Selected material preview"] = "Aperçu du matériau sélectionné",
        ["Tool Material:"] = "Matériau de l'outil :",
        ["Original Material:"] = "Matériau d'origine :",
        ["Current Material:"] = "Matériau actuel :",
        ["Select an NPC, ragdoll, or player. Saved material hides apply to every entity using the same model path."] = "Sélectionnez un PNJ, un ragdoll ou un joueur. Les matériaux masqués enregistrés s'appliquent à toutes les entités utilisant le même chemin de modèle.",
        ["Selected model path"] = "Chemin du modèle sélectionné",
        ["Select a model by left-clicking an NPC, ragdoll, or player."] = "Sélectionnez un modèle par clic gauche sur un PNJ, un ragdoll ou un joueur.",
        ["Select a model by right-clicking an NPC, ragdoll, or player."] = "Sélectionnez un modèle par clic droit sur un PNJ, un ragdoll ou un joueur.",
        ["Select a model by right-clicking an NPC, ragdoll, player, prop, weapon, or viewmodel."] = "Sélectionnez un modèle par clic droit sur un PNJ, un ragdoll, un joueur, un prop, une arme ou un viewmodel.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel. SheepyLord/imported models use importer scope; other targets use exact .mdl path scope."] = "Clic droit sur un PNJ, un ragdoll, un joueur, un prop, une arme ou un viewmodel. Les modèles SheepyLord/importés utilisent la portée importateur ; les autres cibles utilisent le chemin .mdl exact.",
        ["Jigglebone tool for Imported model"] = "Outil jigglebone pour modèle importé",
        ["Disable jigglebones for any model path."] = "Désactive les jigglebones pour n'importe quel chemin de modèle.",
        ["Select an NPC, ragdoll, or player. Saved jigglebone settings apply to every entity using the same model path."] = "Sélectionnez un PNJ, un ragdoll ou un joueur. Les réglages jigglebone enregistrés s'appliquent à toutes les entités utilisant le même chemin de modèle.",
        ["Invalid model path."] = "Chemin de modèle invalide.",
        ["Saved repairs for model path: %s"] = "Réparations enregistrées pour le chemin de modèle : %s",
        ["Spawn model without jigglebone"] = "Créer le modèle sans jigglebone",
        ["When enabled, spawned/imported NPCs, ragdolls, and matching PMs will save and use all jigglebones disabled."] = "Si activé, les PNJ, ragdolls et modèles joueur correspondants créés/importés enregistrent et utilisent tous les jigglebones désactivés.",
    },
    ["es-ES"] = {
        ["Model Importer"] = "Importador de modelos",
        ["Dynamic Model Importer"] = "Importador dinámico de modelos",
        ["Spawn MMD Character Importer models."] = "Genera modelos de MMD Character Importer.",
        ["Select a model in the menu. Left-click the world to spawn an NPC; right-click the world to spawn a ragdoll."] = "Selecciona un modelo en el menú. Haz clic izquierdo en el mundo para generar un NPC; clic derecho para generar un ragdoll.",
        ["Shows models produced by MMD Character Importer. Select a row, then left-click the world to spawn an NPC or right-click the world to spawn a ragdoll."] = "Muestra modelos producidos por MMD Character Importer. Selecciona una fila y luego haz clic izquierdo en el mundo para generar un NPC o clic derecho para generar un ragdoll.",
        ["Refresh model list"] = "Actualizar lista de modelos",
        ["Search models..."] = "Buscar modelos...",
        ["Friendly"] = "Amistoso",
        ["Hostile"] = "Hostil",
        ["Neutral"] = "Neutral",
        ["NPC health"] = "Salud del NPC",
        ["Shotgun"] = "Escopeta",
        ["Pistol"] = "Pistola",
        ["None"] = "Ninguno",
        ["Custom weapon class, for example weapon_smg1"] = "Clase de arma personalizada, por ejemplo weapon_smg1",
        ["Manifest imported models"] = "Modelos importados por manifiesto",
        ["Legacy autorun models"] = "Modelos autorun heredados",
        ["Model"] = "Modelo",
        ["Category"] = "Categoría",
        ["Model path"] = "Ruta del modelo",
        ["PM"] = "Modelo de jugador",
        ["yes"] = "sí",
        ["no"] = "no",
        ["Selected model id"] = "ID de modelo seleccionado",
        ["Spawning only happens from the tool itself: left-click the world for NPC, right-click the world for ragdoll."] = "La generación solo ocurre desde la herramienta: clic izquierdo en el mundo para NPC, clic derecho para ragdoll.",
        ["Model is not available: %s"] = "El modelo no está disponible: %s",
        ["Failed to create NPC class: %s"] = "No se pudo crear la clase de NPC: %s",
        ["Spawned NPC: %s"] = "NPC generado: %s",
        ["Failed to create ragdoll."] = "No se pudo crear el ragdoll.",
        ["Spawned ragdoll: %s"] = "Ragdoll generado: %s",
        ["Could not load model manifest."] = "No se pudo cargar el manifiesto del modelo.",
        ["Invalid model id."] = "ID de modelo no válido.",
        ["Dynamic Model Repair"] = "Reparación de modelos dinámicos",
        ["Repair imported model materials and jiggle bones."] = "Repara materiales y huesos jiggle de modelos importados.",
        ["Select a model in the menu. Save repairs, then spawned NPCs, ragdolls, and matching player models use them automatically."] = "Selecciona un modelo en el menú. Guarda las reparaciones y los NPC, ragdolls y modelos de jugador coincidentes las usarán automáticamente.",
        ["Hide bad materials and disable jiggle bones for Dynamic Model Importer models. Settings are saved server-wide."] = "Oculta materiales problemáticos y desactiva huesos jiggle en modelos de Dynamic Model Importer. Los ajustes se guardan en el servidor.",
        ["Materials"] = "Materiales",
        ["Index"] = "Índice",
        ["Material"] = "Material",
        ["Hidden"] = "Oculto",
        ["Hide selected material"] = "Ocultar material seleccionado",
        ["Restore selected material"] = "Restaurar material seleccionado",
        ["Restore all materials"] = "Restaurar todos los materiales",
        ["Bones"] = "Huesos",
        ["Bone"] = "Hueso",
        ["Parent"] = "Padre",
        ["Children"] = "Hijos",
        ["No jiggle"] = "Sin jiggle",
        ["Essential"] = "Esencial",
        ["locked"] = "bloqueado",
        ["Disable selected bone jiggle"] = "Desactivar jiggle del hueso seleccionado",
        ["Restore selected bone jiggle"] = "Restaurar jiggle del hueso seleccionado",
        ["Disable all jiggle"] = "Desactivar todo el jiggle",
        ["Restore all jiggle"] = "Restaurar todo el jiggle",
        ["1. Select Target"] = "1. Seleccionar objetivo",
        ["Right-click an NPC, ragdoll, or player. Saved jigglebone overrides apply to every entity using that model path."] = "Haz clic derecho en un NPC, ragdoll o jugador. Las anulaciones de jigglebone guardadas se aplican a todas las entidades que usan esa ruta de modelo.",
        ["2. Filter Bones"] = "2. Filtrar huesos",
        ["Filter by bone name keywords and/or a parent/root bone. Subset actions use the currently visible filtered rows."] = "Filtra por palabras clave del nombre del hueso y/o por un hueso padre/raíz. Las acciones de subconjunto usan las filas filtradas visibles.",
        ["Filters decide which bones are shown in the table. Table actions affect every row currently shown."] = "Los filtros deciden qué huesos se muestran en la tabla. Las acciones de tabla afectan a cada fila visible.",
        ["Keyword filter"] = "Filtro de palabra clave",
        ["Parent/root filter"] = "Filtro padre/raíz",
        ["Include descendants"] = "Incluir descendientes",
        ["Hair"] = "Pelo",
        ["Sleeves"] = "Mangas",
        ["Skirt"] = "Falda",
        ["Left side"] = "Lado izquierdo",
        ["Right side"] = "Lado derecho",
        ["Clear filter"] = "Borrar filtro",
        ["3. Bone Table"] = "3. Tabla de huesos",
        ["Disabled jigglebones are marked in red. Left-click in the world toggles all jigglebones for the selected model."] = "Los jigglebones desactivados se marcan en rojo. El clic izquierdo en el mundo alterna todos los jigglebones del modelo seleccionado.",
        ["Disabled jigglebones are marked in red. Locked essential skeleton bones cannot be restored to jiggle."] = "Los jigglebones desactivados se marcan en rojo. Los huesos esenciales bloqueados no se pueden restaurar a jiggle.",
        ["4. Jigglebone Actions"] = "4. Acciones de jigglebone",
        ["Use selected-bone actions for precise fixes, filtered actions for subsets, or bulk actions when the model should have no jiggle at all."] = "Usa las acciones de huesos seleccionados para arreglos precisos, las acciones filtradas para subconjuntos o las acciones globales cuando el modelo no debe tener jiggle.",
        ["Use selected-bone actions for precise fixes, table actions for every row currently shown, or bulk actions when the model should have no jiggle at all. Essential skeleton bones stay locked to no-jiggle."] = "Usa acciones de huesos seleccionados para arreglos precisos, acciones de tabla para todas las filas visibles o acciones globales cuando el modelo no debe tener jiggle. Los huesos esenciales quedan bloqueados sin jiggle.",
        ["Disable filtered bones"] = "Desactivar huesos filtrados",
        ["Restore filtered bones"] = "Restaurar huesos filtrados",
        ["Disable all bones in table"] = "Desactivar todos los huesos de la tabla",
        ["Restore all bones in table"] = "Restaurar todos los huesos de la tabla",
        ["No active filter. Use Disable all jiggle or Restore all jiggle for whole-model changes."] = "No hay filtro activo. Usa Desactivar todo el jiggle o Restaurar todo el jiggle para cambiar todo el modelo.",
        ["No filtered bones matched."] = "No coinciden huesos filtrados.",
        ["No bones in table."] = "No hay huesos en la tabla.",
        ["%d filtered bone(s)."] = "%d hueso(s) filtrado(s).",
        ["%d bone(s) in table."] = "%d hueso(s) en la tabla.",
        ["%d table bone(s)."] = "%d hueso(s) de la tabla.",
        ["Saved repair settings apply to NPCs, ragdolls, and matching player models."] = "Los ajustes de reparación guardados se aplican a NPCs, ragdolls y modelos de jugador coincidentes.",
        ["Select a model first."] = "Primero selecciona un modelo.",
        ["Selected model has no inspectable model path."] = "El modelo seleccionado no tiene una ruta inspeccionable.",
        ["Could not inspect model: %s"] = "No se pudo inspeccionar el modelo: %s",
        ["Loaded repair settings."] = "Ajustes de reparación cargados.",
        ["No material selected."] = "No hay material seleccionado.",
        ["No bone selected."] = "No hay hueso seleccionado.",
        ["Target does not match the selected imported model."] = "El objetivo no coincide con el modelo importado seleccionado.",
        ["Applied saved repairs to target."] = "Reparaciones guardadas aplicadas al objetivo.",
        ["Only admins can save Dynamic Model Importer repairs on this server."] = "Solo los administradores pueden guardar reparaciones de Dynamic Model Importer en este servidor.",
        ["Saved repairs for: %s"] = "Reparaciones guardadas para: %s",
        ["Hide Material Tool for Imported model"] = "Herramienta para ocultar material en modelo importado",
        ["Hide materials for any model path using the Dynamic Model Importer invisible material."] = "Oculta materiales de cualquier ruta de modelo usando el material invisible de Dynamic Model Importer.",
        ["Left-click an NPC, ragdoll, or player to select its model."] = "Haz clic izquierdo en un NPC, ragdoll o jugador para seleccionar su modelo.",
        ["Right-click an NPC, ragdoll, or player to select its model. Left-click toggles the selected material."] = "Haz clic derecho en un NPC, ragdoll o jugador para seleccionar su modelo. El clic izquierdo alterna el material seleccionado.",
        ["Right-click an NPC, ragdoll, or player to select its model. Left-click toggles all jigglebones."] = "Haz clic derecho en un NPC, ragdoll o jugador para seleccionar su modelo. El clic izquierdo alterna todos los jigglebones.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles the selected material."] = "Haz clic derecho en un NPC, ragdoll, jugador, prop, arma o viewmodel para seleccionar su modelo. El clic izquierdo alterna el material seleccionado.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles all jigglebones."] = "Haz clic derecho en un NPC, ragdoll, jugador, prop, arma o viewmodel para seleccionar su modelo. El clic izquierdo alterna todos los jigglebones.",
        ["Target has no valid model path."] = "El objetivo no tiene una ruta de modelo válida.",
        ["Selected model: %s"] = "Modelo seleccionado: %s",
        ["Selected model: %s (%s)"] = "Modelo seleccionado: %s (%s)",
        ["Importer model scope"] = "Ámbito de modelo importado",
        ["Exact model path scope"] = "Ámbito de ruta exacta del modelo",
        ["Importer model scope: saved repairs use the importer model path and continue to work for spawned NPCs, ragdolls, and matching player models."] = "Ámbito de modelo importado: las reparaciones guardadas usan la ruta del modelo importado y siguen funcionando para NPCs, ragdolls y modelos de jugador coincidentes.",
        ["Exact model path scope: saved repairs affect only entities using this exact .mdl path, including matching viewmodels or weapons."] = "Ámbito de ruta exacta: las reparaciones guardadas solo afectan a entidades que usan exactamente esta ruta .mdl, incluidos viewmodels o armas coincidentes.",
        ["Selected material index"] = "Índice de material seleccionado",
        ["Hide current material"] = "Ocultar material actual",
        ["Restore current material"] = "Restaurar material actual",
        ["Selected material preview"] = "Vista previa del material seleccionado",
        ["Tool Material:"] = "Material de la herramienta:",
        ["Original Material:"] = "Material original:",
        ["Current Material:"] = "Material actual:",
        ["Select an NPC, ragdoll, or player. Saved material hides apply to every entity using the same model path."] = "Selecciona un NPC, ragdoll o jugador. Los materiales ocultos guardados se aplican a todas las entidades que usan la misma ruta de modelo.",
        ["Selected model path"] = "Ruta del modelo seleccionado",
        ["Select a model by left-clicking an NPC, ragdoll, or player."] = "Selecciona un modelo con clic izquierdo en un NPC, ragdoll o jugador.",
        ["Select a model by right-clicking an NPC, ragdoll, or player."] = "Selecciona un modelo con clic derecho en un NPC, ragdoll o jugador.",
        ["Select a model by right-clicking an NPC, ragdoll, player, prop, weapon, or viewmodel."] = "Selecciona un modelo con clic derecho en un NPC, ragdoll, jugador, prop, arma o viewmodel.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel. SheepyLord/imported models use importer scope; other targets use exact .mdl path scope."] = "Haz clic derecho en un NPC, ragdoll, jugador, prop, arma o viewmodel. Los modelos SheepyLord/importados usan ámbito de importador; los demás objetivos usan la ruta .mdl exacta.",
        ["Jigglebone tool for Imported model"] = "Herramienta jigglebone para modelo importado",
        ["Disable jigglebones for any model path."] = "Desactiva jigglebones para cualquier ruta de modelo.",
        ["Select an NPC, ragdoll, or player. Saved jigglebone settings apply to every entity using the same model path."] = "Selecciona un NPC, ragdoll o jugador. Los ajustes de jigglebone guardados se aplican a todas las entidades que usan la misma ruta de modelo.",
        ["Invalid model path."] = "Ruta de modelo no válida.",
        ["Saved repairs for model path: %s"] = "Reparaciones guardadas para la ruta de modelo: %s",
        ["Spawn model without jigglebone"] = "Generar modelo sin jigglebone",
        ["When enabled, spawned/imported NPCs, ragdolls, and matching PMs will save and use all jigglebones disabled."] = "Cuando está activado, los NPCs, ragdolls y PMs coincidentes generados/importados guardarán y usarán todos los jigglebones desactivados.",
    },
    ["ko"] = {
        ["Model Importer"] = "모델 가져오기",
        ["Dynamic Model Importer"] = "동적 모델 가져오기",
        ["Spawn MMD Character Importer models."] = "MMD Character Importer 모델을 생성합니다.",
        ["Select a model in the menu. Left-click the world to spawn an NPC; right-click the world to spawn a ragdoll."] = "메뉴에서 모델을 선택하세요. 월드에서 왼쪽 클릭하면 NPC가 생성되고, 오른쪽 클릭하면 래그돌이 생성됩니다.",
        ["Shows models produced by MMD Character Importer. Select a row, then left-click the world to spawn an NPC or right-click the world to spawn a ragdoll."] = "MMD Character Importer에서 만든 모델을 표시합니다. 행을 선택한 뒤 월드에서 왼쪽 클릭으로 NPC를, 오른쪽 클릭으로 래그돌을 생성하세요.",
        ["Refresh model list"] = "모델 목록 새로고침",
        ["Search models..."] = "모델 검색...",
        ["Friendly"] = "우호",
        ["Hostile"] = "적대",
        ["Neutral"] = "중립",
        ["NPC health"] = "NPC 체력",
        ["Shotgun"] = "샷건",
        ["Pistol"] = "권총",
        ["None"] = "없음",
        ["Custom weapon class, for example weapon_smg1"] = "사용자 지정 무기 클래스, 예: weapon_smg1",
        ["Manifest imported models"] = "매니페스트 가져온 모델",
        ["Legacy autorun models"] = "레거시 autorun 모델",
        ["Model"] = "모델",
        ["Category"] = "카테고리",
        ["Model path"] = "모델 경로",
        ["PM"] = "플레이어 모델",
        ["yes"] = "예",
        ["no"] = "아니요",
        ["Selected model id"] = "선택한 모델 ID",
        ["Spawning only happens from the tool itself: left-click the world for NPC, right-click the world for ragdoll."] = "생성은 이 도구에서만 됩니다. 월드에서 왼쪽 클릭은 NPC, 오른쪽 클릭은 래그돌입니다.",
        ["Model is not available: %s"] = "모델을 사용할 수 없습니다: %s",
        ["Failed to create NPC class: %s"] = "NPC 클래스를 만들 수 없습니다: %s",
        ["Spawned NPC: %s"] = "NPC 생성됨: %s",
        ["Failed to create ragdoll."] = "래그돌을 만들 수 없습니다.",
        ["Spawned ragdoll: %s"] = "래그돌 생성됨: %s",
        ["Could not load model manifest."] = "모델 매니페스트를 불러올 수 없습니다.",
        ["Invalid model id."] = "모델 ID가 올바르지 않습니다.",
        ["Dynamic Model Repair"] = "동적 모델 복구",
        ["Repair imported model materials and jiggle bones."] = "가져온 모델의 재질과 지글 본을 복구합니다.",
        ["Select a model in the menu. Save repairs, then spawned NPCs, ragdolls, and matching player models use them automatically."] = "메뉴에서 모델을 선택하세요. 복구를 저장하면 생성된 NPC, 래그돌, 일치하는 플레이어 모델에 자동 적용됩니다.",
        ["Hide bad materials and disable jiggle bones for Dynamic Model Importer models. Settings are saved server-wide."] = "문제가 있는 재질을 숨기고 Dynamic Model Importer 모델의 지글 본을 비활성화합니다. 설정은 서버 전체에 저장됩니다.",
        ["Materials"] = "재질",
        ["Index"] = "인덱스",
        ["Material"] = "재질",
        ["Hidden"] = "숨김",
        ["Hide selected material"] = "선택한 재질 숨기기",
        ["Restore selected material"] = "선택한 재질 복원",
        ["Restore all materials"] = "모든 재질 복원",
        ["Bones"] = "본",
        ["Bone"] = "본",
        ["Parent"] = "부모",
        ["Children"] = "자식",
        ["No jiggle"] = "지글 없음",
        ["Essential"] = "필수",
        ["locked"] = "잠김",
        ["Disable selected bone jiggle"] = "선택한 본 지글 비활성화",
        ["Restore selected bone jiggle"] = "선택한 본 지글 복원",
        ["Disable all jiggle"] = "모든 지글 비활성화",
        ["Restore all jiggle"] = "모든 지글 복원",
        ["1. Select Target"] = "1. 대상 선택",
        ["Right-click an NPC, ragdoll, or player. Saved jigglebone overrides apply to every entity using that model path."] = "NPC, 래그돌 또는 플레이어를 오른쪽 클릭하세요. 저장된 지글본 오버라이드는 해당 모델 경로를 사용하는 모든 엔티티에 적용됩니다.",
        ["2. Filter Bones"] = "2. 본 필터",
        ["Filter by bone name keywords and/or a parent/root bone. Subset actions use the currently visible filtered rows."] = "본 이름 키워드 및/또는 부모/루트 본으로 필터링합니다. 하위 집합 작업은 현재 보이는 필터 행에 적용됩니다.",
        ["Filters decide which bones are shown in the table. Table actions affect every row currently shown."] = "필터는 표에 표시되는 본을 결정합니다. 표 작업은 현재 표시된 모든 행에 적용됩니다.",
        ["Keyword filter"] = "키워드 필터",
        ["Parent/root filter"] = "부모/루트 필터",
        ["Include descendants"] = "하위 본 포함",
        ["Hair"] = "머리카락",
        ["Sleeves"] = "소매",
        ["Skirt"] = "스커트",
        ["Left side"] = "왼쪽",
        ["Right side"] = "오른쪽",
        ["Clear filter"] = "필터 지우기",
        ["3. Bone Table"] = "3. 본 목록",
        ["Disabled jigglebones are marked in red. Left-click in the world toggles all jigglebones for the selected model."] = "비활성화된 지글본은 빨간색으로 표시됩니다. 월드에서 왼쪽 클릭하면 선택한 모델의 모든 지글본을 전환합니다.",
        ["Disabled jigglebones are marked in red. Locked essential skeleton bones cannot be restored to jiggle."] = "비활성화된 지글본은 빨간색으로 표시됩니다. 잠긴 필수 골격 본은 지글로 복원할 수 없습니다.",
        ["4. Jigglebone Actions"] = "4. 지글본 작업",
        ["Use selected-bone actions for precise fixes, filtered actions for subsets, or bulk actions when the model should have no jiggle at all."] = "선택한 본 작업은 정밀 수정에, 필터 작업은 하위 집합에, 전체 작업은 모델의 모든 지글을 없앨 때 사용합니다.",
        ["Use selected-bone actions for precise fixes, table actions for every row currently shown, or bulk actions when the model should have no jiggle at all. Essential skeleton bones stay locked to no-jiggle."] = "선택한 본 작업은 정밀 수정에, 표 작업은 현재 표시된 모든 행에, 전체 작업은 모델의 모든 지글을 없앨 때 사용합니다. 필수 골격 본은 지글 없음으로 잠긴 상태를 유지합니다.",
        ["Disable filtered bones"] = "필터된 본 비활성화",
        ["Restore filtered bones"] = "필터된 본 복원",
        ["Disable all bones in table"] = "표의 모든 본 비활성화",
        ["Restore all bones in table"] = "표의 모든 본 복원",
        ["No active filter. Use Disable all jiggle or Restore all jiggle for whole-model changes."] = "활성 필터가 없습니다. 전체 모델을 변경하려면 모든 지글 비활성화 또는 모든 지글 복원을 사용하세요.",
        ["No filtered bones matched."] = "일치하는 필터 본이 없습니다.",
        ["No bones in table."] = "표에 본이 없습니다.",
        ["%d filtered bone(s)."] = "필터된 본 %d개.",
        ["%d bone(s) in table."] = "표에 본 %d개.",
        ["%d table bone(s)."] = "표 본 %d개.",
        ["Saved repair settings apply to NPCs, ragdolls, and matching player models."] = "저장된 복구 설정은 NPC, 래그돌 및 일치하는 플레이어 모델에 적용됩니다.",
        ["Select a model first."] = "먼저 모델을 선택하세요.",
        ["Selected model has no inspectable model path."] = "선택한 모델에 검사할 수 있는 모델 경로가 없습니다.",
        ["Could not inspect model: %s"] = "모델을 검사할 수 없습니다: %s",
        ["Loaded repair settings."] = "복구 설정을 불러왔습니다.",
        ["No material selected."] = "선택한 재질이 없습니다.",
        ["No bone selected."] = "선택한 본이 없습니다.",
        ["Target does not match the selected imported model."] = "대상이 선택한 가져온 모델과 일치하지 않습니다.",
        ["Applied saved repairs to target."] = "저장된 복구를 대상에 적용했습니다.",
        ["Only admins can save Dynamic Model Importer repairs on this server."] = "관리자만 이 서버에서 Dynamic Model Importer 복구를 저장할 수 있습니다.",
        ["Saved repairs for: %s"] = "복구 저장됨: %s",
        ["Hide Material Tool for Imported model"] = "가져온 모델 재질 숨기기 도구",
        ["Hide materials for any model path using the Dynamic Model Importer invisible material."] = "Dynamic Model Importer 투명 재질을 사용해 모든 모델 경로의 재질을 숨깁니다.",
        ["Left-click an NPC, ragdoll, or player to select its model."] = "NPC, 래그돌 또는 플레이어를 왼쪽 클릭해 모델을 선택하세요.",
        ["Right-click an NPC, ragdoll, or player to select its model. Left-click toggles the selected material."] = "NPC, 래그돌 또는 플레이어를 오른쪽 클릭해 모델을 선택하세요. 왼쪽 클릭은 선택한 재질을 전환합니다.",
        ["Right-click an NPC, ragdoll, or player to select its model. Left-click toggles all jigglebones."] = "NPC, 래그돌 또는 플레이어를 오른쪽 클릭해 모델을 선택하세요. 왼쪽 클릭은 모든 지글본을 전환합니다.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles the selected material."] = "NPC, 래그돌, 플레이어, 프롭, 무기 또는 뷰모델을 오른쪽 클릭해 모델을 선택하세요. 왼쪽 클릭은 선택한 재질을 전환합니다.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles all jigglebones."] = "NPC, 래그돌, 플레이어, 프롭, 무기 또는 뷰모델을 오른쪽 클릭해 모델을 선택하세요. 왼쪽 클릭은 모든 지글본을 전환합니다.",
        ["Target has no valid model path."] = "대상에 유효한 모델 경로가 없습니다.",
        ["Selected model: %s"] = "선택한 모델: %s",
        ["Selected model: %s (%s)"] = "선택한 모델: %s (%s)",
        ["Importer model scope"] = "가져온 모델 범위",
        ["Exact model path scope"] = "정확한 모델 경로 범위",
        ["Importer model scope: saved repairs use the importer model path and continue to work for spawned NPCs, ragdolls, and matching player models."] = "가져온 모델 범위: 저장된 복구 설정은 가져온 모델 경로를 사용하며 생성된 NPC, 래그돌 및 일치하는 플레이어 모델에 계속 적용됩니다.",
        ["Exact model path scope: saved repairs affect only entities using this exact .mdl path, including matching viewmodels or weapons."] = "정확한 모델 경로 범위: 저장된 복구 설정은 일치하는 뷰모델이나 무기를 포함해 이 정확한 .mdl 경로를 사용하는 엔티티에만 적용됩니다.",
        ["Selected material index"] = "선택한 재질 인덱스",
        ["Hide current material"] = "현재 재질 숨기기",
        ["Restore current material"] = "현재 재질 복원",
        ["Selected material preview"] = "선택한 재질 미리보기",
        ["Tool Material:"] = "도구 재질:",
        ["Original Material:"] = "원본 재질:",
        ["Current Material:"] = "현재 재질:",
        ["Select an NPC, ragdoll, or player. Saved material hides apply to every entity using the same model path."] = "NPC, 래그돌 또는 플레이어를 선택하세요. 저장된 재질 숨김은 같은 모델 경로를 사용하는 모든 엔티티에 적용됩니다.",
        ["Selected model path"] = "선택한 모델 경로",
        ["Select a model by left-clicking an NPC, ragdoll, or player."] = "NPC, 래그돌 또는 플레이어를 왼쪽 클릭해 모델을 선택하세요.",
        ["Select a model by right-clicking an NPC, ragdoll, or player."] = "NPC, 래그돌 또는 플레이어를 오른쪽 클릭해 모델을 선택하세요.",
        ["Select a model by right-clicking an NPC, ragdoll, player, prop, weapon, or viewmodel."] = "NPC, 래그돌, 플레이어, 프롭, 무기 또는 뷰모델을 오른쪽 클릭해 모델을 선택하세요.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel. SheepyLord/imported models use importer scope; other targets use exact .mdl path scope."] = "NPC, 래그돌, 플레이어, 프롭, 무기 또는 뷰모델을 오른쪽 클릭하세요. SheepyLord/가져온 모델은 가져온 모델 범위를 사용하고 다른 대상은 정확한 .mdl 경로 범위를 사용합니다.",
        ["Jigglebone tool for Imported model"] = "가져온 모델 지글본 도구",
        ["Disable jigglebones for any model path."] = "모든 모델 경로의 지글본을 비활성화합니다.",
        ["Select an NPC, ragdoll, or player. Saved jigglebone settings apply to every entity using the same model path."] = "NPC, 래그돌 또는 플레이어를 선택하세요. 저장된 지글본 설정은 같은 모델 경로를 사용하는 모든 엔티티에 적용됩니다.",
        ["Invalid model path."] = "모델 경로가 올바르지 않습니다.",
        ["Saved repairs for model path: %s"] = "모델 경로 복구 저장됨: %s",
        ["Spawn model without jigglebone"] = "지글본 없이 모델 생성",
        ["When enabled, spawned/imported NPCs, ragdolls, and matching PMs will save and use all jigglebones disabled."] = "활성화하면 생성/가져온 NPC, 래그돌 및 일치하는 플레이어 모델이 모든 지글본 비활성화 설정을 저장하고 사용합니다.",
    },
    ["ru"] = {
        ["Model Importer"] = "Импорт моделей",
        ["Dynamic Model Importer"] = "Динамический импорт моделей",
        ["Spawn MMD Character Importer models."] = "Создаёт модели MMD Character Importer.",
        ["Select a model in the menu. Left-click the world to spawn an NPC; right-click the world to spawn a ragdoll."] = "Выберите модель в меню. ЛКМ по миру создаёт NPC; ПКМ создаёт рэгдолл.",
        ["Shows models produced by MMD Character Importer. Select a row, then left-click the world to spawn an NPC or right-click the world to spawn a ragdoll."] = "Показывает модели, созданные MMD Character Importer. Выберите строку, затем нажмите ЛКМ по миру для NPC или ПКМ для рэгдолла.",
        ["Refresh model list"] = "Обновить список моделей",
        ["Search models..."] = "Поиск моделей...",
        ["Friendly"] = "Дружественный",
        ["Hostile"] = "Враждебный",
        ["Neutral"] = "Нейтральный",
        ["NPC health"] = "Здоровье NPC",
        ["Shotgun"] = "Дробовик",
        ["Pistol"] = "Пистолет",
        ["None"] = "Нет",
        ["Custom weapon class, for example weapon_smg1"] = "Пользовательский класс оружия, например weapon_smg1",
        ["Manifest imported models"] = "Модели из манифеста",
        ["Legacy autorun models"] = "Устаревшие autorun-модели",
        ["Model"] = "Модель",
        ["Category"] = "Категория",
        ["Model path"] = "Путь модели",
        ["PM"] = "Модель игрока",
        ["yes"] = "да",
        ["no"] = "нет",
        ["Selected model id"] = "ID выбранной модели",
        ["Spawning only happens from the tool itself: left-click the world for NPC, right-click the world for ragdoll."] = "Создание выполняется только этим инструментом: ЛКМ по миру для NPC, ПКМ для рэгдолла.",
        ["Model is not available: %s"] = "Модель недоступна: %s",
        ["Failed to create NPC class: %s"] = "Не удалось создать класс NPC: %s",
        ["Spawned NPC: %s"] = "NPC создан: %s",
        ["Failed to create ragdoll."] = "Не удалось создать рэгдолл.",
        ["Spawned ragdoll: %s"] = "Рэгдолл создан: %s",
        ["Could not load model manifest."] = "Не удалось загрузить манифест модели.",
        ["Invalid model id."] = "Недопустимый ID модели.",
        ["Dynamic Model Repair"] = "Ремонт динамических моделей",
        ["Repair imported model materials and jiggle bones."] = "Исправляет материалы и jiggle-кости импортированных моделей.",
        ["Select a model in the menu. Save repairs, then spawned NPCs, ragdolls, and matching player models use them automatically."] = "Выберите модель в меню. Сохраните исправления; созданные NPC, рэгдоллы и совпадающие модели игрока будут применять их автоматически.",
        ["Hide bad materials and disable jiggle bones for Dynamic Model Importer models. Settings are saved server-wide."] = "Скрывает проблемные материалы и отключает jiggle-кости у моделей Dynamic Model Importer. Настройки сохраняются на сервере.",
        ["Materials"] = "Материалы",
        ["Index"] = "Индекс",
        ["Material"] = "Материал",
        ["Hidden"] = "Скрыт",
        ["Hide selected material"] = "Скрыть выбранный материал",
        ["Restore selected material"] = "Восстановить выбранный материал",
        ["Restore all materials"] = "Восстановить все материалы",
        ["Bones"] = "Кости",
        ["Bone"] = "Кость",
        ["Parent"] = "Родитель",
        ["Children"] = "Дочерние",
        ["No jiggle"] = "Без jiggle",
        ["Essential"] = "Основная",
        ["locked"] = "заблокировано",
        ["Disable selected bone jiggle"] = "Отключить jiggle выбранной кости",
        ["Restore selected bone jiggle"] = "Восстановить jiggle выбранной кости",
        ["Disable all jiggle"] = "Отключить весь jiggle",
        ["Restore all jiggle"] = "Восстановить весь jiggle",
        ["1. Select Target"] = "1. Выбор цели",
        ["Right-click an NPC, ragdoll, or player. Saved jigglebone overrides apply to every entity using that model path."] = "Нажмите ПКМ по NPC, рэгдоллу или игроку. Сохраненные переопределения jigglebone применяются ко всем сущностям с этим путем модели.",
        ["2. Filter Bones"] = "2. Фильтр костей",
        ["Filter by bone name keywords and/or a parent/root bone. Subset actions use the currently visible filtered rows."] = "Фильтрует по ключевым словам имени кости и/или по родительской/корневой кости. Действия подмножества применяются к видимым отфильтрованным строкам.",
        ["Filters decide which bones are shown in the table. Table actions affect every row currently shown."] = "Фильтры определяют, какие кости показаны в таблице. Действия таблицы применяются ко всем видимым строкам.",
        ["Keyword filter"] = "Фильтр по ключевым словам",
        ["Parent/root filter"] = "Фильтр родителя/корня",
        ["Include descendants"] = "Включать потомков",
        ["Hair"] = "Волосы",
        ["Sleeves"] = "Рукава",
        ["Skirt"] = "Юбка",
        ["Left side"] = "Левая сторона",
        ["Right side"] = "Правая сторона",
        ["Clear filter"] = "Очистить фильтр",
        ["3. Bone Table"] = "3. Таблица костей",
        ["Disabled jigglebones are marked in red. Left-click in the world toggles all jigglebones for the selected model."] = "Отключенные jigglebone отмечены красным. ЛКМ в мире переключает все jigglebone выбранной модели.",
        ["Disabled jigglebones are marked in red. Locked essential skeleton bones cannot be restored to jiggle."] = "Отключенные jigglebone отмечены красным. Заблокированные основные кости скелета нельзя вернуть в jiggle.",
        ["4. Jigglebone Actions"] = "4. Действия jigglebone",
        ["Use selected-bone actions for precise fixes, filtered actions for subsets, or bulk actions when the model should have no jiggle at all."] = "Используйте действия с выбранными костями для точных исправлений, фильтрованные действия для подмножеств или массовые действия, когда у модели не должно быть jiggle.",
        ["Use selected-bone actions for precise fixes, table actions for every row currently shown, or bulk actions when the model should have no jiggle at all. Essential skeleton bones stay locked to no-jiggle."] = "Используйте действия с выбранными костями для точных исправлений, действия таблицы для всех видимых строк или массовые действия, когда у модели не должно быть jiggle. Основные кости скелета остаются заблокированными без jiggle.",
        ["Disable filtered bones"] = "Отключить отфильтрованные кости",
        ["Restore filtered bones"] = "Восстановить отфильтрованные кости",
        ["Disable all bones in table"] = "Отключить все кости в таблице",
        ["Restore all bones in table"] = "Восстановить все кости в таблице",
        ["No active filter. Use Disable all jiggle or Restore all jiggle for whole-model changes."] = "Нет активного фильтра. Для изменения всей модели используйте Отключить весь jiggle или Восстановить весь jiggle.",
        ["No filtered bones matched."] = "Нет подходящих отфильтрованных костей.",
        ["No bones in table."] = "В таблице нет костей.",
        ["%d filtered bone(s)."] = "Отфильтровано костей: %d.",
        ["%d bone(s) in table."] = "Костей в таблице: %d.",
        ["%d table bone(s)."] = "Костей таблицы: %d.",
        ["Saved repair settings apply to NPCs, ragdolls, and matching player models."] = "Сохраненные настройки исправлений применяются к NPC, рэгдоллам и совпадающим моделям игрока.",
        ["Select a model first."] = "Сначала выберите модель.",
        ["Selected model has no inspectable model path."] = "У выбранной модели нет пути для проверки.",
        ["Could not inspect model: %s"] = "Не удалось проверить модель: %s",
        ["Loaded repair settings."] = "Настройки исправлений загружены.",
        ["No material selected."] = "Материал не выбран.",
        ["No bone selected."] = "Кость не выбрана.",
        ["Target does not match the selected imported model."] = "Цель не соответствует выбранной импортированной модели.",
        ["Applied saved repairs to target."] = "Сохраненные исправления применены к цели.",
        ["Only admins can save Dynamic Model Importer repairs on this server."] = "Только администраторы могут сохранять исправления Dynamic Model Importer на этом сервере.",
        ["Saved repairs for: %s"] = "Исправления сохранены для: %s",
        ["Hide Material Tool for Imported model"] = "Инструмент скрытия материалов для импортированной модели",
        ["Hide materials for any model path using the Dynamic Model Importer invisible material."] = "Скрывает материалы для любого пути модели с помощью невидимого материала Dynamic Model Importer.",
        ["Left-click an NPC, ragdoll, or player to select its model."] = "Нажмите ЛКМ по NPC, рэгдоллу или игроку, чтобы выбрать его модель.",
        ["Right-click an NPC, ragdoll, or player to select its model. Left-click toggles the selected material."] = "Нажмите ПКМ по NPC, рэгдоллу или игроку, чтобы выбрать его модель. ЛКМ переключает выбранный материал.",
        ["Right-click an NPC, ragdoll, or player to select its model. Left-click toggles all jigglebones."] = "Нажмите ПКМ по NPC, рэгдоллу или игроку, чтобы выбрать его модель. ЛКМ переключает все jigglebone.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles the selected material."] = "Нажмите ПКМ по NPC, рэгдоллу, игроку, prop, оружию или viewmodel, чтобы выбрать его модель. ЛКМ переключает выбранный материал.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel to select its model. Left-click toggles all jigglebones."] = "Нажмите ПКМ по NPC, рэгдоллу, игроку, prop, оружию или viewmodel, чтобы выбрать его модель. ЛКМ переключает все jigglebone.",
        ["Target has no valid model path."] = "У цели нет допустимого пути модели.",
        ["Selected model: %s"] = "Выбрана модель: %s",
        ["Selected model: %s (%s)"] = "Выбрана модель: %s (%s)",
        ["Importer model scope"] = "Область импортированной модели",
        ["Exact model path scope"] = "Область точного пути модели",
        ["Importer model scope: saved repairs use the importer model path and continue to work for spawned NPCs, ragdolls, and matching player models."] = "Область импортированной модели: сохраненные исправления используют путь модели импортера и продолжают работать для созданных NPC, рэгдоллов и совпадающих моделей игрока.",
        ["Exact model path scope: saved repairs affect only entities using this exact .mdl path, including matching viewmodels or weapons."] = "Область точного пути: сохраненные исправления влияют только на сущности с этим точным путем .mdl, включая совпадающие viewmodel или оружие.",
        ["Selected material index"] = "Индекс выбранного материала",
        ["Hide current material"] = "Скрыть текущий материал",
        ["Restore current material"] = "Восстановить текущий материал",
        ["Selected material preview"] = "Предпросмотр выбранного материала",
        ["Tool Material:"] = "Материал инструмента:",
        ["Original Material:"] = "Исходный материал:",
        ["Current Material:"] = "Текущий материал:",
        ["Select an NPC, ragdoll, or player. Saved material hides apply to every entity using the same model path."] = "Выберите NPC, рэгдолл или игрока. Сохраненные скрытия материалов применяются ко всем сущностям с тем же путем модели.",
        ["Selected model path"] = "Выбранный путь модели",
        ["Select a model by left-clicking an NPC, ragdoll, or player."] = "Выберите модель, нажав ЛКМ по NPC, рэгдоллу или игроку.",
        ["Select a model by right-clicking an NPC, ragdoll, or player."] = "Выберите модель, нажав ПКМ по NPC, рэгдоллу или игроку.",
        ["Select a model by right-clicking an NPC, ragdoll, player, prop, weapon, or viewmodel."] = "Выберите модель, нажав ПКМ по NPC, рэгдоллу, игроку, prop, оружию или viewmodel.",
        ["Right-click an NPC, ragdoll, player, prop, weapon, or viewmodel. SheepyLord/imported models use importer scope; other targets use exact .mdl path scope."] = "Нажмите ПКМ по NPC, рэгдоллу, игроку, prop, оружию или viewmodel. Модели SheepyLord/импортированные используют область импортера; остальные цели используют точный путь .mdl.",
        ["Jigglebone tool for Imported model"] = "Инструмент jigglebone для импортированной модели",
        ["Disable jigglebones for any model path."] = "Отключает jigglebone для любого пути модели.",
        ["Select an NPC, ragdoll, or player. Saved jigglebone settings apply to every entity using the same model path."] = "Выберите NPC, рэгдолл или игрока. Сохраненные настройки jigglebone применяются ко всем сущностям с тем же путем модели.",
        ["Invalid model path."] = "Недопустимый путь модели.",
        ["Saved repairs for model path: %s"] = "Исправления сохранены для пути модели: %s",
        ["Spawn model without jigglebone"] = "Создавать модель без jigglebone",
        ["When enabled, spawned/imported NPCs, ragdolls, and matching PMs will save and use all jigglebones disabled."] = "Если включено, созданные/импортированные NPC, рэгдоллы и совпадающие модели игрока сохранят и будут использовать отключенные jigglebone.",
    },
}

local DMI_LANGUAGE_ALIASES = {
    cn = "zh-CN",
    ["zh"] = "zh-CN",
    ["zh-cn"] = "zh-CN",
    ["zh_hans"] = "zh-CN",
    ["zh-hans"] = "zh-CN",
    ["schinese"] = "zh-CN",
    ["chinese"] = "zh-CN",
    ["zh-tw"] = "zh-CN",
    ["tchinese"] = "zh-CN",
    fr = "fr",
    french = "fr",
    es = "es-ES",
    ["es-es"] = "es-ES",
    spanish = "es-ES",
    ko = "ko",
    ["ko-kr"] = "ko",
    koreana = "ko",
    korean = "ko",
    ru = "ru",
    russian = "ru",
}

function DynamicModelImporter.NormalizeLanguageCode(raw)
    local normalized = tostring(raw or "en"):lower():gsub("_", "-")
    return DMI_LANGUAGE_ALIASES[normalized] or DMI_LANGUAGE_ALIASES[normalized:match("^[^%-]+") or ""] or "en"
end

function DynamicModelImporter.LanguageCode()
    if not CLIENT then return "en" end
    return DynamicModelImporter.NormalizeLanguageCode(GetConVarString("gmod_language") or "en")
end

function DynamicModelImporter.L(raw)
    local text = tostring(raw or "")
    if not CLIENT then return text end
    local languageTable = DynamicModelImporter.Translations[DynamicModelImporter.LanguageCode()]
    if languageTable and languageTable[text] then
        return languageTable[text]
    end
    return text
end

function DynamicModelImporter.LF(raw, ...)
    local ok, formatted = pcall(string.format, DynamicModelImporter.L(raw), ...)
    if ok then return formatted end
    return DynamicModelImporter.L(raw)
end

function DynamicModelImporter.RepairScopeLabel(modelPath)
    local scope = DynamicModelImporter.RepairScopeForModelPath(modelPath)
    if scope == "importer" then
        return DynamicModelImporter.L("Importer model scope")
    elseif scope == "exact" then
        return DynamicModelImporter.L("Exact model path scope")
    end
    return DynamicModelImporter.L("Invalid model path.")
end

function DynamicModelImporter.RepairScopeStatus(modelPath)
    local scope = DynamicModelImporter.RepairScopeForModelPath(modelPath)
    if scope == "importer" then
        return DynamicModelImporter.L("Importer model scope: saved repairs use the importer model path and continue to work for spawned NPCs, ragdolls, and matching player models.")
    elseif scope == "exact" then
        return DynamicModelImporter.L("Exact model path scope: saved repairs affect only entities using this exact .mdl path, including matching viewmodels or weapons.")
    end
    return DynamicModelImporter.L("Invalid model path.")
end

if CLIENT then
    DynamicModelImporter.UI = DynamicModelImporter.UI or {}
    DynamicModelImporter.UI.Colors = {
        Panel = Color(24, 28, 34, 236),
        PanelSoft = Color(31, 36, 44, 224),
        Border = Color(71, 83, 99, 180),
        Text = Color(236, 241, 248),
        Muted = Color(164, 176, 190),
        Blue = Color(76, 162, 255),
        Green = Color(77, 200, 136),
        Orange = Color(255, 170, 70),
        Red = Color(255, 104, 104),
        Purple = Color(174, 132, 255),
    }

    function DynamicModelImporter.UI.AddSection(panel, title, description, accent)
        accent = accent or DynamicModelImporter.UI.Colors.Blue
        local box = vgui.Create("DPanel")
        box:SetTall(description and 68 or 38)
        box:DockPadding(12, 8, 10, 8)
        box.Paint = function(_, width, height)
            draw.RoundedBox(6, 0, 0, width, height, DynamicModelImporter.UI.Colors.Panel)
            draw.RoundedBoxEx(6, 0, 0, 5, height, accent, true, false, true, false)
            surface.SetDrawColor(DynamicModelImporter.UI.Colors.Border)
            surface.DrawOutlinedRect(0, 0, width, height)
        end

        local titleLabel = vgui.Create("DLabel", box)
        titleLabel:Dock(TOP)
        titleLabel:SetText(DynamicModelImporter.L(title))
        titleLabel:SetFont("DermaDefaultBold")
        titleLabel:SetTextColor(accent)
        titleLabel:SizeToContents()

        if description and description ~= "" then
            local descLabel = vgui.Create("DLabel", box)
            descLabel:Dock(FILL)
            descLabel:DockMargin(0, 4, 0, 0)
            descLabel:SetWrap(true)
            descLabel:SetText(DynamicModelImporter.L(description))
            descLabel:SetTextColor(DynamicModelImporter.UI.Colors.Muted)
        end

        panel:AddItem(box)
        return box
    end

    function DynamicModelImporter.UI.AddStatus(panel, text, accent)
        local label = vgui.Create("DLabel")
        label:SetWrap(true)
        label:SetAutoStretchVertical(true)
        label:SetText(DynamicModelImporter.L(text or ""))
        label:SetTextColor(accent or DynamicModelImporter.UI.Colors.Text)
        panel:AddItem(label)
        return label
    end

    function DynamicModelImporter.UI.StyleButton(button, accent, textColor)
        if not IsValid(button) then return button end
        accent = accent or DynamicModelImporter.UI.Colors.Blue
        textColor = textColor or color_white
        button:SetTall(math.max(button:GetTall(), 26))
        button:SetTextColor(textColor)
        button.Paint = function(self, width, height)
            local bg = accent
            local disabled = self.GetDisabled and self:GetDisabled() or false
            if disabled then
                bg = Color(80, 80, 80)
            elseif self.Depressed then
                bg = Color(math.max(accent.r - 38, 0), math.max(accent.g - 38, 0), math.max(accent.b - 38, 0), accent.a)
            elseif self:IsHovered() then
                bg = Color(math.min(accent.r + 22, 255), math.min(accent.g + 22, 255), math.min(accent.b + 22, 255), accent.a)
            end
            draw.RoundedBox(5, 0, 0, width, height, bg)
            draw.SimpleText(self:GetText(), "DermaDefaultBold", width / 2, height / 2, textColor, TEXT_ALIGN_CENTER, TEXT_ALIGN_CENTER)
            return true
        end
        return button
    end

    function DynamicModelImporter.UI.StyleList(list)
        if not IsValid(list) then return list end
        list.Paint = function(_, width, height)
            draw.RoundedBox(4, 0, 0, width, height, Color(18, 21, 26, 220))
            surface.SetDrawColor(DynamicModelImporter.UI.Colors.Border)
            surface.DrawOutlinedRect(0, 0, width, height)
        end
        return list
    end
end

local function starts_with(value, prefix)
    return string.sub(value, 1, #prefix) == prefix
end

local function trim(value)
    return tostring(value or ""):match("^%s*(.-)%s*$") or ""
end

function DynamicModelImporter.NormalizeID(raw)
    raw = tostring(raw or ""):lower()
    raw = raw:gsub("\\", "/")
    raw = raw:gsub("%.json$", "")
    raw = raw:gsub("^/+", "")
    raw = raw:gsub("/+$", "")
    raw = raw:gsub("[^a-z0-9_%-/]", "")
    if raw == "" then return nil end
    if string.find(raw, "../", 1, true) or string.find(raw, "..\\", 1, true) then return nil end
    if string.find(raw, "//", 1, true) then return nil end
    return raw
end

function DynamicModelImporter.NormalizeModelPath(raw)
    raw = tostring(raw or "")
    raw = raw:gsub("\\", "/")
    raw = raw:gsub("^/+", "")
    raw = trim(raw)
    local lower = string.lower(raw)
    if raw == "" then return nil end
    if string.find(raw, "..", 1, true) then return nil end
    if not starts_with(lower, "models/") then return nil end
    if not string.match(lower, "%.mdl$") then return nil end
    return raw
end

local function warn(message)
    print("[Dynamic Model Importer] " .. tostring(message))
end

local function manifest_to_entry(manifest, fallbackID)
    if not istable(manifest) then return nil end
    local paths = istable(manifest.paths) and manifest.paths or {}
    local modelPath = DynamicModelImporter.NormalizeModelPath(paths.model or manifest.model_path)
    if not modelPath then return nil end
    local id = DynamicModelImporter.NormalizeID(manifest.manifest_id or manifest.model_id or fallbackID)
    if not id then return nil end
    local pmPath = DynamicModelImporter.NormalizeModelPath(paths.player_model or manifest.player_model_path or "")
    return {
        model_id = id,
        display_name = tostring(manifest.display_name or manifest.model_name or id),
        category_readable = tostring(manifest.category_readable or manifest.character_category or ""),
        character_category = tostring(manifest.character_category or ""),
        author = tostring(manifest.author or ""),
        model_path = modelPath,
        player_model_path = pmPath or "",
        has_player_model = pmPath ~= nil and pmPath ~= "",
        arms_model_path = DynamicModelImporter.NormalizeModelPath(paths.arms_model or "") or "",
        friendly_icon = tostring(paths.friendly_icon or ""),
        enemy_icon = tostring(paths.enemy_icon or ""),
        npc_defaults = istable(manifest.npc_defaults) and manifest.npc_defaults or {},
        legacy = tobool(manifest.legacy),
    }
end

local parse_legacy_autorun

function DynamicModelImporter.LoadManifest(modelID)
    local safeID = DynamicModelImporter.NormalizeID(modelID)
    if not safeID then return nil, "Invalid model id." end
    local path = DynamicModelImporter.StaticRoot .. "/" .. safeID .. ".json"
    local raw = file.Read(path, "GAME")
    if not raw then
        if parse_legacy_autorun then
            local legacy = parse_legacy_autorun("lua/autorun/" .. safeID .. ".lua")
            if legacy then return legacy end
            local legacyFiles = file.Find(DynamicModelImporter.LegacyAutorunPattern, "GAME", "nameasc")
            for _, name in ipairs(legacyFiles or {}) do
                if DynamicModelImporter.NormalizeID(name) == safeID then
                    legacy = parse_legacy_autorun("lua/autorun/" .. name)
                    if legacy then return legacy end
                end
            end
        end
        return nil, "Manifest not found: " .. path
    end
    local parsed = util.JSONToTable(raw, true, true)
    local entry = manifest_to_entry(parsed, safeID)
    if not entry then return nil, "Manifest is invalid: " .. path end
    return entry
end

local function add_seen(results, seen, entry)
    if not entry or not entry.model_id or seen[entry.model_id] then return end
    seen[entry.model_id] = true
    results[#results + 1] = entry
end

local function legacy_id_from_path(path)
    local name = tostring(path or ""):match("([^/\\]+)%.lua$") or tostring(path or "")
    return DynamicModelImporter.NormalizeID(name)
end

parse_legacy_autorun = function(path)
    local raw = file.Read(path, "GAME")
    if not raw then return nil end
    local display, pmPath = raw:match('player_manager%.AddValidModel%(%s*"([^"]+)"%s*,%s*"([^"]+)"')
    local category = raw:match('local%s+Category%s*=%s*"([^"]+)"') or ""
    local modelPath = raw:match('Model%s*=%s*"([^"]+%.mdl)"')
    local id = legacy_id_from_path(path)
    if not modelPath or not id then return nil end
    local manifest = {
        manifest_id = id,
        display_name = display or id,
        category_readable = category,
        paths = {
            model = modelPath,
            player_model = pmPath or "",
        },
        legacy = true,
        -- Mirror the data_static manifest schema: spawn_npc reads the
        -- per-relation specs for class/keyvalues. Without citizentype = 4,
        -- npc_citizen swaps custom models for models/Humans/Group01/<name>.mdl.
        npc_defaults = {
            relation = "friendly",
            health = 100,
            weapon = "weapon_smg1",
            friendly = {
                class = "npc_citizen",
                weapon = "weapon_smg1",
                keyvalues = { citizentype = "4" },
            },
            hostile = {
                class = "npc_combine_s",
                weapon = "weapon_ar2",
                keyvalues = { Numgrenades = "4" },
            },
            neutral = {
                class = "npc_citizen",
                weapon = "weapon_smg1",
                keyvalues = { citizentype = "4" },
            },
        },
    }
    return manifest_to_entry(manifest, id)
end

function DynamicModelImporter.ListAvailableModels()
    local results = {}
    local seen = {}
    local files = file.Find(DynamicModelImporter.StaticRoot .. "/*.json", "GAME", "nameasc")
    for _, name in ipairs(files or {}) do
        local id = DynamicModelImporter.NormalizeID(name)
        if id then
            local entry, err = DynamicModelImporter.LoadManifest(id)
            if entry then
                add_seen(results, seen, entry)
            elseif err then
                warn(err)
            end
        end
    end

    local legacyFiles = file.Find(DynamicModelImporter.LegacyAutorunPattern, "GAME", "nameasc")
    for _, name in ipairs(legacyFiles or {}) do
        local entry = parse_legacy_autorun("lua/autorun/" .. name)
        add_seen(results, seen, entry)
    end

    table.sort(results, function(a, b)
        local ac = string.lower(a.category_readable or "")
        local bc = string.lower(b.category_readable or "")
        if ac ~= bc then return ac < bc end
        return string.lower(a.display_name or a.model_id or "") < string.lower(b.display_name or b.model_id or "")
    end)
    return results
end

local function sanitize_relation(value)
    value = string.lower(tostring(value or "friendly"))
    if value ~= "friendly" and value ~= "hostile" and value ~= "neutral" then
        return "friendly"
    end
    return value
end

local function sanitize_weapon(value)
    value = tostring(value or ""):gsub("[^%w_]", "")
    -- "none" is an explicit request to spawn unarmed; "" means "use the
    -- manifest's default weapon".
    if string.lower(value) == "none" then
        return "none"
    end
    if value ~= "" and not starts_with(value, "weapon_") then
        return ""
    end
    return value
end

local function safe_health(value)
    return math.Clamp(math.floor(tonumber(value) or 100), 1, 9999)
end

local function valid_model_for_spawn(modelPath)
    if not DynamicModelImporter.NormalizeModelPath(modelPath) then return false end
    if util and util.IsValidModel then
        return util.IsValidModel(modelPath)
    end
    return file.Exists(modelPath, "GAME")
end

local function sanitize_submaterial_index(value)
    local index = tonumber(value)
    if not index then return nil end
    index = math.floor(index)
    if index < 0 or index > 255 then return nil end
    return index
end

local function sanitize_bone_name(value)
    value = trim(value)
    value = value:gsub("[%c]", "")
    if value == "" then return nil end
    return string.sub(value, 1, 128)
end

function DynamicModelImporter.NormalizeOverrideModelPath(raw)
    local modelPath = DynamicModelImporter.NormalizeModelPath(raw or "")
    if not modelPath then return nil end
    return string.lower(modelPath)
end

function DynamicModelImporter.IsImporterModelPath(modelPath)
    local safePath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath or "")
    if not safePath then return false end
    return starts_with(safePath, "models/sheepylord/")
end

function DynamicModelImporter.RepairScopeForModelPath(modelPath)
    local safePath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath or "")
    if not safePath then return nil end
    if DynamicModelImporter.IsImporterModelPath(safePath) then
        return "importer"
    end
    return "exact"
end

function DynamicModelImporter.EntityModelPath(ent)
    if not IsValid(ent) or not ent.GetModel then return nil end
    return DynamicModelImporter.NormalizeOverrideModelPath(ent:GetModel() or "")
end

function DynamicModelImporter.EmptyModelOverride()
    return {
        hidden_submaterials = {},
        no_jiggle = {
            all = false,
            bones = {},
        },
    }
end

function DynamicModelImporter.SanitizeModelOverride(raw)
    raw = istable(raw) and raw or {}
    local result = DynamicModelImporter.EmptyModelOverride()
    local hidden = istable(raw.hidden_submaterials) and raw.hidden_submaterials or {}
    for key, value in pairs(hidden) do
        local index = sanitize_submaterial_index(key)
        if index and value ~= false and value ~= nil and tostring(value) ~= "" then
            result.hidden_submaterials[tostring(index)] = DynamicModelImporter.InvisibleMaterialPath
        end
    end

    local noJiggle = istable(raw.no_jiggle) and raw.no_jiggle or {}
    result.no_jiggle.all = tobool(noJiggle.all)
    if not result.no_jiggle.all and istable(noJiggle.bones) then
        for key, value in pairs(noJiggle.bones) do
            local boneName
            if isnumber(key) and isstring(value) then
                boneName = sanitize_bone_name(value)
            elseif value ~= false and value ~= nil then
                boneName = sanitize_bone_name(key)
            end
            if boneName then
                result.no_jiggle.bones[boneName] = true
            end
        end
    end
    return result
end

function DynamicModelImporter.ModelOverrideIsEmpty(override)
    override = DynamicModelImporter.SanitizeModelOverride(override)
    if next(override.hidden_submaterials) then return false end
    if override.no_jiggle.all then return false end
    if next(override.no_jiggle.bones) then return false end
    return true
end

function DynamicModelImporter.MergeModelOverrides(base, incoming)
    base = DynamicModelImporter.SanitizeModelOverride(base)
    incoming = DynamicModelImporter.SanitizeModelOverride(incoming)
    for key, value in pairs(incoming.hidden_submaterials) do
        base.hidden_submaterials[key] = value
    end
    if incoming.no_jiggle.all then
        base.no_jiggle.all = true
        base.no_jiggle.bones = {}
    elseif not base.no_jiggle.all then
        for key, value in pairs(incoming.no_jiggle.bones) do
            base.no_jiggle.bones[key] = value
        end
    end
    return base
end

local function normalized_manifest_paths(manifest)
    if not istable(manifest) then return {} end
    local paths = {}
    local modelPath = DynamicModelImporter.NormalizeOverrideModelPath(manifest.model_path or "")
    local playerPath = DynamicModelImporter.NormalizeOverrideModelPath(manifest.player_model_path or "")
    if modelPath then paths[modelPath] = true end
    if playerPath then paths[playerPath] = true end
    return paths
end

function DynamicModelImporter.EntityMatchesManifest(ent, manifest)
    local modelPath = DynamicModelImporter.EntityModelPath(ent)
    if not modelPath then return false end
    return normalized_manifest_paths(manifest)[modelPath] == true
end

function DynamicModelImporter.FindManifestForModelPath(modelPath)
    modelPath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath or "")
    if not modelPath then return nil end
    for _, entry in ipairs(DynamicModelImporter.ListAvailableModels() or {}) do
        if normalized_manifest_paths(entry)[modelPath] then
            return entry
        end
    end
    return nil
end

function DynamicModelImporter.ManifestModelPaths(manifest)
    local results = {}
    local seen = {}
    for path in pairs(normalized_manifest_paths(manifest)) do
        if not seen[path] then
            seen[path] = true
            results[#results + 1] = path
        end
    end
    table.sort(results)
    return results
end

local function lookup_bone_case_insensitive(ent, boneName)
    if not IsValid(ent) or not ent.LookupBone then return nil end
    local index = ent:LookupBone(boneName)
    if isnumber(index) and index >= 0 then return index end
    if not ent.GetBoneCount or not ent.GetBoneName then return nil end
    local wanted = string.lower(tostring(boneName or ""))
    for i = 0, math.max((ent:GetBoneCount() or 0) - 1, -1) do
        if string.lower(tostring(ent:GetBoneName(i) or "")) == wanted then
            return i
        end
    end
    return nil
end

function DynamicModelImporter.ApplyOverrideToEntity(ent, override)
    if not IsValid(ent) then return false end
    override = DynamicModelImporter.SanitizeModelOverride(override)

    if ent.GetMaterials and ent.SetSubMaterial then
        local materialCount = #(ent:GetMaterials() or {})
        local activeHidden = {}
        local previousHidden = ent.DynamicModelImporterHiddenSubmaterials or {}
        for key in pairs(previousHidden) do
            if not override.hidden_submaterials[key] then
                ent:SetSubMaterial(tonumber(key) or 0, "")
            end
        end
        for key in pairs(override.hidden_submaterials) do
            local index = sanitize_submaterial_index(key)
            if index and index < materialCount then
                ent:SetSubMaterial(index, DynamicModelImporter.InvisibleMaterialPath)
                activeHidden[tostring(index)] = true
            end
        end
        ent.DynamicModelImporterHiddenSubmaterials = next(activeHidden) and activeHidden or nil
    end

    if ent.ManipulateBoneJiggle and ent.GetBoneCount then
        local targetBones = {}
        local boneCount = ent:GetBoneCount() or 0
        if override.no_jiggle.all then
            for i = 0, math.max(boneCount - 1, -1) do
                targetBones[tostring(i)] = true
            end
        else
            for boneName in pairs(override.no_jiggle.bones) do
                local index = lookup_bone_case_insensitive(ent, boneName)
                if index then
                    targetBones[tostring(index)] = true
                end
            end
        end

        local previousBones = ent.DynamicModelImporterNoJiggleBones or {}
        for key in pairs(previousBones) do
            if not targetBones[key] then
                ent:ManipulateBoneJiggle(tonumber(key) or 0, 0)
            end
        end
        for key in pairs(targetBones) do
            ent:ManipulateBoneJiggle(tonumber(key) or 0, 2)
        end
        ent.DynamicModelImporterNoJiggleBones = next(targetBones) and targetBones or nil
    end

    return true
end

if SERVER then
    local modelOverrideCache

    function DynamicModelImporter.CanEditOverrides(ply)
        if not IsValid(ply) then return false end
        if game.SinglePlayer and game.SinglePlayer() then return true end
        if ply.IsListenServerHost and ply:IsListenServerHost() then return true end
        return ply:IsAdmin()
    end

    function DynamicModelImporter.LoadModelOverrides()
        if modelOverrideCache then return modelOverrideCache end
        local parsed
        local raw = file.Read(DynamicModelImporter.OverrideDataPath, "DATA")
        if raw then
            parsed = util.JSONToTable(raw, true, true)
        end
        modelOverrideCache = {
            version = 2,
            model_paths = {},
        }

        local function add_path_override(modelPath, override)
            local safePath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
            if not safePath then return end
            local sanitized = DynamicModelImporter.SanitizeModelOverride(override)
            if DynamicModelImporter.ModelOverrideIsEmpty(sanitized) then return end
            modelOverrideCache.model_paths[safePath] = DynamicModelImporter.MergeModelOverrides(modelOverrideCache.model_paths[safePath], sanitized)
        end

        if istable(parsed) and istable(parsed.model_paths) then
            for modelPath, override in pairs(parsed.model_paths) do
                add_path_override(modelPath, override)
            end
        end

        if istable(parsed) and istable(parsed.models) then
            for modelID, override in pairs(parsed.models) do
                local directPath = DynamicModelImporter.NormalizeOverrideModelPath(modelID)
                if directPath then
                    add_path_override(directPath, override)
                else
                    local safeID = DynamicModelImporter.NormalizeID(modelID)
                    if safeID then
                        local manifest = DynamicModelImporter.LoadManifest(safeID)
                        if manifest then
                            for _, modelPath in ipairs(DynamicModelImporter.ManifestModelPaths(manifest)) do
                                add_path_override(modelPath, override)
                            end
                        end
                    end
                end
            end
        end
        return modelOverrideCache
    end

    function DynamicModelImporter.SaveModelOverrides()
        local data = DynamicModelImporter.LoadModelOverrides()
        file.CreateDir("dynamic_model_importer")
        file.Write(DynamicModelImporter.OverrideDataPath, util.TableToJSON(data, true) or "{}")
    end

    function DynamicModelImporter.GetModelPathOverride(modelPath)
        local safePath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
        if not safePath then return DynamicModelImporter.EmptyModelOverride() end
        local data = DynamicModelImporter.LoadModelOverrides()
        return DynamicModelImporter.SanitizeModelOverride(data.model_paths[safePath])
    end

    function DynamicModelImporter.SetModelPathOverride(modelPath, override)
        local safePath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
        if not safePath then return nil, "Invalid model path." end
        local data = DynamicModelImporter.LoadModelOverrides()
        local sanitized = DynamicModelImporter.SanitizeModelOverride(override)
        if DynamicModelImporter.ModelOverrideIsEmpty(sanitized) then
            data.model_paths[safePath] = nil
        else
            data.model_paths[safePath] = sanitized
        end
        DynamicModelImporter.SaveModelOverrides()
        return DynamicModelImporter.GetModelPathOverride(safePath)
    end

    function DynamicModelImporter.GetModelOverride(modelID)
        local manifest = DynamicModelImporter.LoadManifest(modelID)
        if not manifest then return DynamicModelImporter.EmptyModelOverride() end
        return DynamicModelImporter.GetModelPathOverride(manifest.model_path)
    end

    function DynamicModelImporter.SetModelOverride(modelID, override)
        local manifest = DynamicModelImporter.LoadManifest(modelID)
        if not manifest then return nil, "Invalid model id." end
        local saved
        for _, modelPath in ipairs(DynamicModelImporter.ManifestModelPaths(manifest)) do
            saved = DynamicModelImporter.SetModelPathOverride(modelPath, override)
        end
        return saved or DynamicModelImporter.EmptyModelOverride()
    end

    function DynamicModelImporter.EnsureNoJiggleForModelPath(modelPath)
        local current = DynamicModelImporter.GetModelPathOverride(modelPath)
        current.no_jiggle.all = true
        current.no_jiggle.bones = {}
        return DynamicModelImporter.SetModelPathOverride(modelPath, current)
    end

    function DynamicModelImporter.EnsureNoJiggleForManifest(manifest)
        if not istable(manifest) then return end
        for _, modelPath in ipairs(DynamicModelImporter.ManifestModelPaths(manifest)) do
            DynamicModelImporter.EnsureNoJiggleForModelPath(modelPath)
        end
    end

    function DynamicModelImporter.ApplySavedOverrideToEntity(ent, manifest)
        if not IsValid(ent) then return false end
        return DynamicModelImporter.ApplyOverrideToEntity(ent, DynamicModelImporter.GetModelPathOverride(DynamicModelImporter.EntityModelPath(ent)))
    end

    function DynamicModelImporter.ApplySavedOverrideForEntityModel(ent)
        if not IsValid(ent) then return false end
        return DynamicModelImporter.ApplySavedOverrideToEntity(ent)
    end

    function DynamicModelImporter.ApplySavedOverridesForModelPath(modelPath)
        local safePath = DynamicModelImporter.NormalizeOverrideModelPath(modelPath)
        if not safePath then return 0 end
        local applied = 0
        for _, ent in ipairs(ents.GetAll() or {}) do
            if DynamicModelImporter.EntityModelPath(ent) == safePath then
                if DynamicModelImporter.ApplySavedOverrideToEntity(ent) then
                    applied = applied + 1
                end
            end
        end
        return applied
    end

    function DynamicModelImporter.ApplySavedOverridesForModel(modelID)
        local manifest = DynamicModelImporter.LoadManifest(modelID)
        if not manifest then return 0 end
        local applied = 0
        for _, modelPath in ipairs(DynamicModelImporter.ManifestModelPaths(manifest)) do
            applied = applied + DynamicModelImporter.ApplySavedOverridesForModelPath(modelPath)
        end
        return applied
    end

    function DynamicModelImporter.Chat(ply, message, ...)
        if IsValid(ply) then
            local args = {...}
            if net then
                net.Start("dynamic_model_importer_chat")
                    net.WriteString(tostring(message))
                    net.WriteUInt(math.min(#args, 8), 4)
                    for i = 1, math.min(#args, 8) do
                        net.WriteString(tostring(args[i]))
                    end
                net.Send(ply)
            else
                ply:ChatPrint("[Dynamic Model Importer] " .. DynamicModelImporter.LF(message, unpack(args)))
            end
        end
    end

    local function chat(ply, message, ...)
        DynamicModelImporter.Chat(ply, message, ...)
    end

    local function apply_npc_relationship(npc, ply, relation)
        local disp = D_LI
        if relation == "hostile" then
            disp = D_HT
        elseif relation == "neutral" then
            disp = D_NU
        end
        if npc.AddEntityRelationship then
            npc:AddEntityRelationship(ply, disp, 99)
        end
        if ply.AddEntityRelationship then
            ply:AddEntityRelationship(npc, disp, 99)
        end
    end

    local function spawn_position(ply, trace)
        trace = istable(trace) and trace or ply:GetEyeTrace()
        local pos = trace.HitPos + trace.HitNormal * 12
        local ang = Angle(0, ply:EyeAngles().y + 180, 0)
        return pos, ang
    end

    local function npc_spec(manifest, relation)
        local defaults = istable(manifest.npc_defaults) and manifest.npc_defaults or {}
        local spec = istable(defaults[relation]) and defaults[relation] or {}
        if relation == "hostile" then
            return spec.class or "npc_combine_s", spec
        end
        return spec.class or "npc_citizen", spec
    end

    local function spawn_npc(ply, manifest, relation, health, weapon, trace)
        local modelPath = manifest.model_path
        if not valid_model_for_spawn(modelPath) then
            chat(ply, "Model is not available: %s", modelPath)
            return false
        end
        local class, spec = npc_spec(manifest, relation)
        local ent = ents.Create(class)
        if not IsValid(ent) then
            chat(ply, "Failed to create NPC class: %s", class)
            return false
        end
        local pos, ang = spawn_position(ply, trace)
        ent:SetPos(pos)
        ent:SetAngles(ang)
        ent:SetModel(modelPath)
        local hasCitizenType = false
        for key, val in pairs(istable(spec.keyvalues) and spec.keyvalues or {}) do
            ent:SetKeyValue(tostring(key), tostring(val))
            if string.lower(tostring(key)) == "citizentype" then
                hasCitizenType = true
            end
        end
        if class == "npc_citizen" and not hasCitizenType then
            -- CT_UNIQUE: without this npc_citizen replaces custom models with
            -- its default models/Humans/Group01 set on Spawn().
            ent:SetKeyValue("citizentype", "4")
        end
        if weapon ~= "" then
            ent:SetKeyValue("additionalequipment", weapon)
        end
        ent:Spawn()
        ent:Activate()
        ent:SetHealth(health)
        if ent.SetMaxHealth then ent:SetMaxHealth(health) end
        DynamicModelImporter.ApplySavedOverrideToEntity(ent, manifest)
        if weapon ~= "" and ent.Give then
            pcall(function() ent:Give(weapon) end)
        end
        apply_npc_relationship(ent, ply, relation)
        ent:DropToFloor()
        undo.Create("Dynamic Model Importer NPC")
            undo.AddEntity(ent)
            undo.SetPlayer(ply)
        undo.Finish()
        cleanup.Add(ply, "npcs", ent)
        chat(ply, "Spawned NPC: %s", manifest.display_name or manifest.model_id)
        return true
    end

    local function spawn_ragdoll(ply, manifest, trace)
        local modelPath = manifest.model_path
        if not valid_model_for_spawn(modelPath) then
            chat(ply, "Model is not available: %s", modelPath)
            return false
        end
        local ent = ents.Create("prop_ragdoll")
        if not IsValid(ent) then
            chat(ply, "Failed to create ragdoll.")
            return false
        end
        local pos, ang = spawn_position(ply, trace)
        ent:SetPos(pos)
        ent:SetAngles(ang)
        ent:SetModel(modelPath)
        ent:Spawn()
        ent:Activate()
        DynamicModelImporter.ApplySavedOverrideToEntity(ent, manifest)
        local phys = ent:GetPhysicsObject()
        if IsValid(phys) then phys:Wake() end
        undo.Create("Dynamic Model Importer Ragdoll")
            undo.AddEntity(ent)
            undo.SetPlayer(ply)
        undo.Finish()
        cleanup.Add(ply, "ragdolls", ent)
        chat(ply, "Spawned ragdoll: %s", manifest.display_name or manifest.model_id)
        return true
    end

    function DynamicModelImporter.SpawnFromRequest(ply, modelID, action, relation, health, weapon, trace, spawnNoJiggle)
        local manifest, err = DynamicModelImporter.LoadManifest(modelID)
        if not manifest then
            chat(ply, err or "Could not load model manifest.")
            return false
        end
        if tobool(spawnNoJiggle) then
            DynamicModelImporter.EnsureNoJiggleForManifest(manifest)
        end
        action = string.lower(tostring(action or "npc"))
        relation = sanitize_relation(relation)
        health = safe_health(health)
        weapon = sanitize_weapon(weapon)
        if action == "ragdoll" then
            return spawn_ragdoll(ply, manifest, trace)
        end
        if weapon == "none" then
            -- Explicit "None": spawn unarmed instead of falling back to the
            -- manifest's default weapon.
            weapon = ""
        elseif weapon == "" then
            local defaults = istable(manifest.npc_defaults) and manifest.npc_defaults or {}
            local relationSpec = istable(defaults[relation]) and defaults[relation] or {}
            weapon = sanitize_weapon(relationSpec.weapon or defaults.weapon or "")
            if weapon == "none" then weapon = "" end
        end
        return spawn_npc(ply, manifest, relation, health, weapon, trace)
    end

    local function apply_player_model_overrides(ply)
        if not IsValid(ply) then return end
        if tobool(ply:GetInfo("dynamic_model_importer_spawn_no_jiggle")) then
            local manifest = DynamicModelImporter.FindManifestForModelPath(ply:GetModel() or "")
            if manifest then
                DynamicModelImporter.EnsureNoJiggleForManifest(manifest)
            end
        end
        DynamicModelImporter.ApplySavedOverrideForEntityModel(ply)
    end

    hook.Add("PlayerSpawn", "DynamicModelImporterApplyPlayerOverrides", function(ply)
        timer.Simple(0, function()
            apply_player_model_overrides(ply)
        end)
    end)

    hook.Add("PlayerSetModel", "DynamicModelImporterApplyPlayerSetModelOverrides", function(ply)
        timer.Simple(0, function()
            apply_player_model_overrides(ply)
        end)
    end)
end
