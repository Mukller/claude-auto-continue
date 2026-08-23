# -*- coding: utf-8 -*-
"""Глубокий аудит: поиск tk-доступов из фоновых потоков."""
import re, sys

src = open('claude_continue_gui.py', encoding='utf-8').read()
lines = src.splitlines(keepends=True)

# Методы, которые выполняются в ФОНОВЫХ потоках
bg_methods = set()
for i, line in enumerate(lines):
    if 'threading.Thread(target=' in line:
        # ищем def <name> выше
        for j in range(i, max(0, i - 5), -1):
            m = re.match(r'    def (\w+)\(', lines[j])
            if m:
                bg_methods.add(m.group(1))
                break

# Также функции верхнего уровня, вызываемые из потоков
for name in ['_run_cycle_impl', '_find_limit_in_all_chats_impl',
             '_lt_scan_impl', 'run_cycle']:
    bg_methods.add(name)

print('Фоновые методы:', sorted(bg_methods))
print()

# Для каждого bg-метода ищем опасные вызовы в его теле
issues = []
i = 0
while i < len(lines):
    line = lines[i]
    m = re.match(r'    def (\w+)\(', line)
    if m and m.group(1) in bg_methods:
        fname = m.group(1)
        # тело до следующего def того же уровня
        j = i + 1
        while j < len(lines):
            l2 = lines[j]
            if re.match(r'    (def |# ─|@)', l2) and not l2.strip().startswith('#'):
                break
            j += 1
        body = ''.join(lines[i:j])
        # прямой доступ к v_*/chk_*/sp_* переменным (tk) без _sgv/_sg обёртки
        for vm in re.finditer(r'self\.(v_\w+|chk_\w+|lbl_\w+|btn_\w+|'
                              r'sp_\w+|ring|log)\b'
                              r'(?!.*(?:root\.after|_slog|_badge))', body):
            ctx = body[max(0, vm.start()-40):vm.end()+40]
            # исключаем присваивания в __init__-стиле и root.after-обёртки
            if '.after(' in ctx or '= tk.' in ctx or 'def ' in ctx.split(vm.group(0))[0][-20:]:
                continue
            issues.append(f'  {fname}: {vm.group(0)} -> {vm.group(0)}')
        i = j
    else:
        i += 1

if issues:
    print('ПОТЕНЦИАЛЬНЫЕ ПРОБЛЕМЫ:')
    for x in set(issues):
        print(x)
else:
    print('Прямых tk-доступов из фоновых методов не найдено')
