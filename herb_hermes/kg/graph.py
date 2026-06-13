"""Build a typed herb knowledge graph from structured herb entries.

Node types: ``herb``, ``meridian`` (歸經), ``nature`` (性味), ``function``
(功效). Edges are labeled relations. The graph is a plain adjacency structure
(no third-party graph library) and exports to node-link JSON and Graphviz DOT
for Cytoscape / ECharts / G6 front-ends.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from ..models import HerbEntry

# A compact lexicon of common 功效 terms used to attach function nodes.
FUNCTION_LEXICON = [
    "補氣", "補血", "補陰", "補陽", "益氣", "養血", "滋陰", "助陽", "固表",
    "健脾", "和胃", "養胃", "生津", "潤肺", "止咳", "化痰", "平喘", "清熱",
    "瀉火", "解毒", "涼血", "活血", "化瘀", "止血", "行氣", "理氣", "疏肝",
    "利水", "滲濕", "燥濕", "祛風", "散寒", "解表", "發汗", "安神", "鎮驚",
    "止痛", "通絡", "強筋骨", "壯筋骨", "補肝腎", "益精", "固精", "縮尿",
    "明目", "聰耳", "生肌", "斂瘡", "托毒", "消腫", "軟堅", "散結",
    "續筋", "接骨", "墮胎", "安胎", "通乳", "下乳", "殺虫", "止瀉", "澀腸",
    "溫中", "回陽", "納氣", "降逆", "開竅", "醒脾", "退黃", "通便", "潤腸",
]

_MERIDIAN_RE = re.compile(r"(心包|大腸|小腸|膀胱|三焦|心|肝|脾|肺|腎|胃|膽)經?")
_NATURE_RE = re.compile(r"(大寒|微寒|寒|大熱|熱|微溫|溫|涼|平)")
_FLAVOR_RE = re.compile(r"(甘|苦|辛|酸|鹹|淡|澀)")


class HerbGraph:
    def __init__(self) -> None:
        # node id -> {type, label}
        self.nodes: Dict[str, Dict[str, str]] = {}
        # (src, rel, dst)
        self.edges: Set[Tuple[str, str, str]] = set()
        self._adj: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    def _add_node(self, label: str, ntype: str) -> str:
        nid = f"{ntype}:{label}"
        if nid not in self.nodes:
            self.nodes[nid] = {"type": ntype, "label": label}
        return nid

    def _add_edge(self, src: str, rel: str, dst: str) -> None:
        if (src, rel, dst) in self.edges:
            return
        self.edges.add((src, rel, dst))
        self._adj[src].append((rel, dst))
        self._adj[dst].append((f"~{rel}", src))

    def add_herb(self, entry: HerbEntry, surface_map: Dict[str, str]) -> None:
        """Add a herb and its attributes.

        ``surface_map`` maps every known surface form (aliases, corpus names)
        to its canonical name so the node and its 配伍 partners are canonical.
        """
        canonical = surface_map.get(entry.name, entry.name)
        herb_id = self._add_node(canonical, "herb")

        for mer in set(_MERIDIAN_RE.findall(entry.meridians or entry.nature_flavor)):
            self._add_edge(herb_id, "歸經", self._add_node(mer + "經", "meridian"))

        nf = entry.nature_flavor
        for nat in set(_NATURE_RE.findall(nf)):
            self._add_edge(herb_id, "性", self._add_node(nat, "nature"))
        for fla in set(_FLAVOR_RE.findall(nf)):
            self._add_edge(herb_id, "味", self._add_node(fla, "nature"))

        haystack = " ".join([entry.functions, entry.indications, entry.category])
        for func in FUNCTION_LEXICON:
            if func in haystack:
                self._add_edge(herb_id, "功效", self._add_node(func, "function"))

        # herb-herb compatibility (药对) from the 配伍 field.
        comp = entry.compatibility or ""
        if comp:
            seen_partners = set()
            for surface, canon in surface_map.items():
                if len(surface) >= 2 and canon != canonical and surface in comp:
                    if canon not in seen_partners:
                        seen_partners.add(canon)
                        self._add_edge(herb_id, "配伍", self._add_node(canon, "herb"))

    def neighbors(self, label: str, ntype: str = "herb") -> List[Dict[str, str]]:
        nid = f"{ntype}:{label}"
        out = []
        for rel, dst in self._adj.get(nid, []):
            node = self.nodes.get(dst, {})
            out.append({"relation": rel, "type": node.get("type", ""), "label": node.get("label", "")})
        return out

    def herbs_sharing_function(self, func: str) -> List[str]:
        nid = f"function:{func}"
        return [self.nodes[src]["label"]
                for rel, src in self._adj.get(nid, []) if rel == "~功效"]

    # ---- export --------------------------------------------------------
    def to_node_link(self) -> Dict:
        return {
            "nodes": [{"id": nid, **attrs} for nid, attrs in self.nodes.items()],
            "links": [{"source": s, "relation": r, "target": d} for s, r, d in sorted(self.edges)],
        }

    def to_dot(self, max_edges: int = 2000) -> str:
        lines = ["digraph HerbHermes {", '  rankdir=LR; node [shape=box, fontname="SimSun"];']
        for i, (s, r, d) in enumerate(sorted(self.edges)):
            if i >= max_edges:
                break
            sl = self.nodes[s]["label"]
            dl = self.nodes[d]["label"]
            lines.append(f'  "{sl}" -> "{dl}" [label="{r}"];')
        lines.append("}")
        return "\n".join(lines)

    @property
    def stats(self) -> Dict[str, int]:
        by_type: Dict[str, int] = defaultdict(int)
        for a in self.nodes.values():
            by_type[a["type"]] += 1
        return {"nodes": len(self.nodes), "edges": len(self.edges), **by_type}
