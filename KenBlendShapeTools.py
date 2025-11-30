import maya.cmds as cmds
import re

source_mesh_memory = [None]

def get_blendshape_node(mesh):
    history = cmds.listHistory(mesh, future=False) or []
    return next((h for h in history if cmds.nodeType(h) == "blendShape"), None)

def get_target_components_and_deltas(blendshape_node, target_index, mesh):
    base_attr = f"{blendshape_node}.inputTarget[0].inputTargetGroup[{target_index}].inputTargetItem[6000]"
    comp_attr = base_attr + ".inputComponentsTarget"
    point_attr = base_attr + ".inputPointsTarget"

    if not cmds.objExists(comp_attr) or not cmds.objExists(point_attr):
        return {}

    components = cmds.getAttr(comp_attr)
    deltas = cmds.getAttr(point_attr)
    if isinstance(deltas[0], (float, int)):
        deltas = [deltas]

    delta_dict = {}
    idx = 0
    for c in components:
        full = f"{mesh}.{c}"
        result = cmds.filterExpand(full, sm=31) or []
        for r in result:
            comp = r.split(".")[-1]
            delta_dict[comp] = deltas[idx]
            idx += 1

    return delta_dict

def update_blendshape_target(blendshape_node, target_index, delta_dict):
    base_attr = f"{blendshape_node}.inputTarget[0].inputTargetGroup[{target_index}].inputTargetItem[6000]"
    point_attr = base_attr + ".inputPointsTarget"
    cmds.setAttr(point_attr, len(delta_dict), *list(delta_dict.values()), type="pointArray")

    comp_attr = base_attr + ".inputComponentsTarget"
    cmds.setAttr(comp_attr, len(delta_dict), *delta_dict, type="componentList")

def reset_selected_blendshape_deltas():
    sel = cmds.ls(sl=True, fl=True)
    verts = cmds.polyListComponentConversion(sel, toVertex=True)
    sel_verts = cmds.filterExpand(verts, sm=31) or []
    if not sel_verts:
        cmds.warning("頂点を選択してください。")
        return

    mesh = sel_verts[0].split('.')[0]
    selected_indices = [int(re.search(r'\[(\d+)\]', v).group(1)) for v in sel_verts]

    blendshape_node = get_blendshape_node(mesh)
    if not blendshape_node:
        cmds.warning("blendShapeノードが見つかりません。")
        return

    num_targets = cmds.getAttr(blendshape_node + ".weight", size=True)
    for t in range(num_targets):
        if cmds.getAttr(f"{blendshape_node}.weight[{t}]") != 1.0:
            continue

        delta_dict = get_target_components_and_deltas(blendshape_node, t, mesh)
        if not delta_dict:
            continue

        for idx in selected_indices:
            key = f"vtx[{idx}]"
            if key in delta_dict:
                delta_dict[key] = [0.0, 0.0, 0.0, 1.0]

        update_blendshape_target(blendshape_node, t, delta_dict)
        print(f"ターゲット {t} の選択頂点の変形をリセットしました。")

def remember_source_mesh():
    sel = cmds.ls(selection=True, long=True)
    if len(sel) != 1:
        cmds.warning("1つのソースメッシュを選択してください。")
        return
    source_mesh_memory[0] = sel[0]
    cmds.text("sourceMeshLabel", edit=True, label=f"ソース: {sel[0]}")
    print(f"ソースメッシュ '{sel[0]}' を記憶しました。")

import time

def apply_deltas_from_source_to_target():
    start_time = time.time()  # 計測開始

    if not source_mesh_memory[0]:
        cmds.warning("まず 'Getソース' ボタンでソースメッシュを記憶してください。")
        return

    sel = cmds.ls(sl=True, fl=True)
    verts = cmds.polyListComponentConversion(sel, toVertex=True)
    sel_verts = cmds.filterExpand(verts, sm=31) or []
    if not sel_verts:
        cmds.warning("頂点を選択してください。")
        return

    source_mesh = source_mesh_memory[0]
    target_mesh = sel_verts[0].split('.')[0]
    selected_indices = [int(re.search(r'\[(\d+)\]', v).group(1)) for v in sel_verts]

    target_orig = next(s for s in (cmds.listRelatives(target_mesh, shapes=True, fullPath=True) or []) if cmds.getAttr(s + ".intermediateObject"))
    if not target_orig:
        cmds.warning("ターゲットメッシュのOrigノードが見つかりません。")
        return

    blendshape_node = get_blendshape_node(target_mesh)
    if not blendshape_node:
        cmds.warning("blendShapeノードが見つかりません。")
        return

    target_index = next((i for i in range(cmds.getAttr(blendshape_node + ".weight", size=True))
                         if cmds.getAttr(f"{blendshape_node}.weight[{i}]") == 1.0), None)
    if target_index is None:
        cmds.warning("ウェイトが1.0のターゲットが見つかりません。")
        return

    delta_dict = get_target_components_and_deltas(blendshape_node, target_index, target_mesh)
    if not delta_dict:
        return

    for idx in selected_indices:
        source_pos = cmds.xform(f"{source_mesh}.vtx[{idx}]", q=True, os=True, t=True)
        target_pos = cmds.xform(f"{target_orig}.vtx[{idx}]", q=True, os=True, t=True)
        delta_dict[f"vtx[{idx}]"] = [s - t for s, t in zip(source_pos, target_pos)] + [1.0]

    update_blendshape_target(blendshape_node, target_index, delta_dict)

    elapsed = time.time() - start_time  # 経過時間
    print(f"ターゲット {target_index} にソースとの差分を適用しました。処理時間: {elapsed:.4f} 秒")

def zero_all_blendshape_weights():
    sel = cmds.ls(selection=True, long=True)
    if not sel:
        cmds.warning("メッシュを選択してください。")
        return

    mesh = sel[0]
    blendshape_node = get_blendshape_node(mesh)
    if not blendshape_node:
        cmds.warning("blendShapeノードが見つかりません。")
        return

    num_targets = cmds.getAttr(blendshape_node + ".weight", size=True)
    for i in range(num_targets):
        cmds.setAttr(f"{blendshape_node}.weight[{i}]", 0.0)
    print("全てのブレンドシェイプターゲットのウェイトを0に設定しました。")

def select_vertices_by_half(half='left'):
    sel = cmds.ls(selection=True, long=True)
    if not sel:
        cmds.warning("メッシュを選択してください。")
        return

    verts = cmds.polyListComponentConversion(sel, toVertex=True)
    verts = cmds.filterExpand(verts, sm=31) or []
    to_select = []
    for v in verts:
        pos = cmds.xform(v, q=True, os=True, t=True)
        if (half == 'left' and pos[0] < 0.00001) or (half == 'right' and pos[0] > -0.00001):
            to_select.append(v)

    cmds.select(to_select, replace=True)

def show_reset_blendshape_ui():
    if cmds.window("resetBlendshapeWin", exists=True):
        cmds.deleteUI("resetBlendshapeWin")

    win = cmds.window("resetBlendshapeWin", title="ブレンドシェイプ変形リセットツール", widthHeight=(400, 150))
    cmds.columnLayout(rowSpacing=8)
    buttonWidth = 180
    cmds.button(label="選択頂点リセット", command=lambda x: reset_selected_blendshape_deltas(),width=buttonWidth)
    cmds.rowLayout(numberOfColumns=2)
    cmds.button(label="R選択", command=lambda x: select_vertices_by_half('left'),width=buttonWidth/2-1)
    cmds.button(label="L選択", command=lambda x: select_vertices_by_half('right'),width=buttonWidth/2-1)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
    cmds.button(label="Getソース", command=lambda x: remember_source_mesh(),width=buttonWidth/2-1)
    cmds.button(label="Move差分", command=lambda x: apply_deltas_from_source_to_target(),width=buttonWidth/2-1)
    cmds.setParent("..")

    cmds.text("sourceMeshLabel", label="ソース: None", align="left")
    cmds.button(label="全ウェイト0", command=lambda x: zero_all_blendshape_weights(),width=buttonWidth)

    cmds.setParent("..")
    cmds.showWindow(win)

show_reset_blendshape_ui()

