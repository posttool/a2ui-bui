// Shared Blender-style menu list renderer (imperative DOM, used inside
// popup() boxes by Area, Dropdown, MenuButton, MenuBar, IDSelector ...).
//
// menuList(box, {title, items, onPick, search}) where items are normalized
// or raw menu items: {label, icon?, shortcut?, value?, description?,
// enabled?, checked?, items? (submenu)} or {separator: true}. Typing filters
// every item (Blender menu search); arrow keys + Enter navigate.

import {popup} from '../base.js';
import {iconGlyph} from '../icons.js';

function iconSpan(name) {
  const s = document.createElement('span');
  if (!name) {
    s.className = 'bui-icon-blank';
    return s;
  }
  s.className = 'bui-icon';
  s.textContent = iconGlyph(name);
  return s;
}

export function menuList(box, {title = '', items = [], onPick, search = true} = {}) {
  const menu = document.createElement('div');
  menu.className = 'bui-menu';
  menu.tabIndex = -1;
  box.appendChild(menu);
  let query = '';
  let hot = -1;
  let rows = [];
  let subClose = null;

  const flat = (list, trail = []) => list.flatMap((it) => {
    if (!it || it.separator) return [];
    if (Array.isArray(it.items)) return flat(it.items, [...trail, it.label]);
    return [{...it, _trail: trail}];
  });

  const draw = () => {
    menu.textContent = '';
    rows = [];
    if (title || query) {
      const t = document.createElement('div');
      t.className = 'bui-menu-title';
      t.textContent = query ? `Search: ${query}` : title;
      menu.appendChild(t);
    }
    const list = query ?
        flat(items).filter((it) => `${it._trail.join(' ')} ${it.label}`.toLowerCase().includes(query.toLowerCase())) :
        items;
    for (const it of list) {
      if (!it) continue;
      if (it.separator) {
        const s = document.createElement('div');
        s.className = 'bui-menu-sep';
        menu.appendChild(s);
        continue;
      }
      const row = document.createElement('div');
      row.className = 'bui-menu-item' + (it.enabled === false ? ' bui-off' : '');
      row.setAttribute('role', 'menuitem');
      if (it.description) row.dataset.tip = it.description;
      row.appendChild(iconSpan(it.checked ? 'CHECKMARK' : it.icon));
      const txt = document.createElement('span');
      txt.className = 'bui-txt';
      txt.textContent = query && it._trail?.length ? `${it._trail.join(' ▸ ')} ▸ ${it.label}` : String(it.label ?? '');
      row.appendChild(txt);
      if (it.shortcut) {
        const sc = document.createElement('span');
        sc.className = 'bui-shortcut';
        sc.textContent = it.shortcut;
        row.appendChild(sc);
      }
      const hasSub = !query && Array.isArray(it.items);
      if (hasSub) {
        const sub = iconSpan('RIGHTARROW');
        sub.classList.add('bui-sub');
        row.appendChild(sub);
        row.addEventListener('pointerenter', () => openSub(row, it));
      } else {
        row.addEventListener('pointerenter', () => {
          subClose?.();
          subClose = null;
        });
        row.addEventListener('click', (e) => {
          e.stopPropagation();
          onPick?.(it);
        });
      }
      menu.appendChild(row);
      rows.push({row, it, hasSub});
    }
    setHot(query ? 0 : -1);
  };

  const openSub = (row, it) => {
    subClose?.();
    subClose = popup(row, (b, close) => menuList(b, {items: it.items, onPick: (x) => {
      close();
      onPick?.(x);
    }, search: false}), {placement: 'right'});
  };

  const setHot = (i) => {
    hot = i;
    rows.forEach((r, j) => r.row.classList.toggle('bui-hot', j === i));
  };

  if (search) {
    menu.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (!rows.length) return;
        const d = e.key === 'ArrowDown' ? 1 : -1;
        setHot((hot + d + rows.length) % rows.length);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const r = rows[hot];
        if (r && !r.hasSub) onPick?.(r.it);
      } else if (e.key === 'Backspace') {
        query = query.slice(0, -1);
        draw();
      } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
        query += e.key;
        draw();
      }
    });
    requestAnimationFrame(() => menu.focus({preventScroll: true}));
  }
  draw();
  return menu;
}
