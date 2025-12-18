import json
from datetime import datetime

class PatternEngine:
    def __init__(self):
        self.patterns = []
        
    def load_patterns(self, patterns_list):
        self.patterns = patterns_list
    
    def normalize_color(self, color, treat_yellow_as_green):
        if treat_yellow_as_green and color == 'yellow':
            return 'green'
        return color
    
    def color_matches_group(self, color, group, treat_yellow_as_green):
        normalized = self.normalize_color(color, treat_yellow_as_green)
        for g in group:
            if g == 'green_yellow':
                if normalized in ['green', 'yellow'] or color in ['green', 'yellow']:
                    return True
            elif g == normalized or g == color:
                return True
        return False

    def _replace_x_expr(self, value, x):
        if not isinstance(value, str):
            return value
        if '$X' not in value:
            return value

        expr = value.replace('$X', str(x)).strip()
        try:
            # allow only digits and +- operators
            for ch in expr:
                if ch not in '0123456789+- ':
                    return value
            return int(eval(expr, {'__builtins__': {}}, {}))
        except Exception:
            return value
    
    def match_sequence(self, colors, sequence, treat_yellow_as_green):
        if not colors or not sequence:
            return False
        
        i = len(colors) - 1
        
        for step in reversed(sequence):
            if i < 0:
                return False
            
            group = step.get('colors', [])
            operator = step.get('operator', 'minimum')
            count_spec = step.get('count', 1)

            if isinstance(count_spec, str):
                try:
                    count = int(count_spec)
                except Exception:
                    return False
            else:
                count = int(count_spec)
            matched = 0
            
            while i >= 0 and self.color_matches_group(colors[i], group, treat_yellow_as_green):
                matched += 1
                i -= 1
            
            if operator == 'exact':
                if matched != count:
                    return False
            elif operator == 'minimum':
                if matched < count:
                    return False
            elif operator == 'maximum':
                if matched > count:
                    return False
        
        return True
    
    def expand_dynamic_pattern(self, pattern_rule):
        if pattern_rule.get('type') != 'dynamic':
            return [pattern_rule]
        
        dynamic_values = pattern_rule.get('dynamic_values', [3,4,5,6,7,8])
        expanded = []
        
        for x in dynamic_values:
            new_rule = json.loads(json.dumps(pattern_rule))
            new_rule['name'] = f"{pattern_rule['name']} (X={x})"
            new_rule['dynamic_x'] = x
            
            if 'trigger' in new_rule and 'steps' in new_rule['trigger']:
                for step in new_rule['trigger']['steps']:
                    step['count'] = self._replace_x_expr(step.get('count'), x)
            
            if 'miss' in new_rule and 'steps' in new_rule['miss']:
                for step in new_rule['miss']['steps']:
                    step['count'] = self._replace_x_expr(step.get('count'), x)
            
            expanded.append(new_rule)
        
        return expanded
    
    def check_pattern(self, colors, pattern_rule):
        treat_yellow_as_green = pattern_rule.get('treat_yellow_as_green', True)
        
        trigger_seq = pattern_rule.get('trigger', {}).get('steps', [])
        miss_seq = pattern_rule.get('miss', {}).get('steps', [])
        
        trigger_match = self.match_sequence(colors, trigger_seq, treat_yellow_as_green)
        miss_match = self.match_sequence(colors, miss_seq, treat_yellow_as_green)
        
        return {
            'trigger': trigger_match,
            'miss': miss_match
        }
    
    def process_round(self, colors, pattern_stats):
        results = []
        
        for pattern_id, rule in self.patterns:
            if not rule.get('active', True):
                continue
            
            stat = pattern_stats.get(pattern_id, {
                'trigger_streak': 0,
                'miss_streak': 0,
                'total_triggers': 0,
                'total_misses': 0,
                'longest_trigger_streak': 0,
                'longest_miss_streak': 0
            })
            
            check = self.check_pattern(colors, rule)
            
            if check['trigger']:
                stat['trigger_streak'] += 1
                stat['miss_streak'] = 0
                stat['total_triggers'] += 1
                if stat['trigger_streak'] > stat['longest_trigger_streak']:
                    stat['longest_trigger_streak'] = stat['trigger_streak']
                
                results.append({
                    'pattern_id': pattern_id,
                    'event': 'trigger',
                    'streak': stat['trigger_streak'],
                    'stats': stat.copy()
                })
            elif check['miss']:
                stat['miss_streak'] += 1
                stat['trigger_streak'] = 0
                stat['total_misses'] += 1
                if stat['miss_streak'] > stat['longest_miss_streak']:
                    stat['longest_miss_streak'] = stat['miss_streak']
                
                results.append({
                    'pattern_id': pattern_id,
                    'event': 'miss',
                    'streak': stat['miss_streak'],
                    'stats': stat.copy()
                })
            
            pattern_stats[pattern_id] = stat
        
        return results


DEFAULT_PATTERNS = [
    {
        "name": "Pattern 1",
        "description": "3+ green/yellow -> 1 red -> 1+ green/yellow (trigger); 3+ green/yellow -> 2+ red (miss)",
        "type": "static",
        "treat_yellow_as_green": True,
        "trigger": {
            "steps": [
                {"colors": ["green_yellow"], "operator": "minimum", "count": 3},
                {"colors": ["red"], "operator": "exact", "count": 1},
                {"colors": ["green_yellow"], "operator": "minimum", "count": 1}
            ]
        },
        "miss": {
            "steps": [
                {"colors": ["green_yellow"], "operator": "minimum", "count": 3},
                {"colors": ["red"], "operator": "minimum", "count": 2}
            ]
        },
        "active": True
    },
    {
        "name": "Pattern 2",
        "description": "3+ green/yellow -> exactly 2 red -> 1+ green/yellow (trigger)",
        "type": "static",
        "treat_yellow_as_green": True,
        "trigger": {
            "steps": [
                {"colors": ["green_yellow"], "operator": "minimum", "count": 3},
                {"colors": ["red"], "operator": "exact", "count": 2},
                {"colors": ["green_yellow"], "operator": "minimum", "count": 1}
            ]
        },
        "miss": {
            "steps": [
                {"colors": ["green_yellow"], "operator": "minimum", "count": 3},
                {"colors": ["red"], "operator": "minimum", "count": 3}
            ]
        },
        "active": True
    },
    {
        "name": "Pattern 3",
        "description": "3+ red -> 1 green/yellow -> 1+ red (trigger)",
        "type": "static",
        "treat_yellow_as_green": True,
        "trigger": {
            "steps": [
                {"colors": ["red"], "operator": "minimum", "count": 3},
                {"colors": ["green_yellow"], "operator": "exact", "count": 1},
                {"colors": ["red"], "operator": "minimum", "count": 1}
            ]
        },
        "miss": {
            "steps": [
                {"colors": ["red"], "operator": "minimum", "count": 3},
                {"colors": ["green_yellow"], "operator": "minimum", "count": 2}
            ]
        },
        "active": True
    },
    {
        "name": "Pattern 4",
        "description": "3+ red -> exactly 2 green/yellow -> 1+ red (trigger)",
        "type": "static",
        "treat_yellow_as_green": True,
        "trigger": {
            "steps": [
                {"colors": ["red"], "operator": "minimum", "count": 3},
                {"colors": ["green_yellow"], "operator": "exact", "count": 2},
                {"colors": ["red"], "operator": "minimum", "count": 1}
            ]
        },
        "miss": {
            "steps": [
                {"colors": ["red"], "operator": "minimum", "count": 3},
                {"colors": ["green_yellow"], "operator": "minimum", "count": 3}
            ]
        },
        "active": True
    },
    {
        "name": "Pattern 5",
        "description": "yellow -> red -> green/yellow (trigger)",
        "type": "static",
        "treat_yellow_as_green": False,
        "trigger": {
            "steps": [
                {"colors": ["yellow"], "operator": "exact", "count": 1},
                {"colors": ["red"], "operator": "exact", "count": 1},
                {"colors": ["green_yellow"], "operator": "minimum", "count": 1}
            ]
        },
        "miss": {
            "steps": [
                {"colors": ["yellow"], "operator": "exact", "count": 1},
                {"colors": ["red"], "operator": "minimum", "count": 2}
            ]
        },
        "active": True
    },
    {
        "name": "Pattern 6",
        "description": "exact X green/yellow where X in [3-8] (dynamic)",
        "type": "dynamic",
        "treat_yellow_as_green": True,
        "dynamic_values": [3, 4, 5, 6, 7, 8],
        "trigger": {
            "steps": [
                {"colors": ["green_yellow"], "operator": "exact", "count": "$X"}
            ]
        },
        "miss": {
            "steps": [
                {"colors": ["green_yellow"], "operator": "minimum", "count": "$X+1"}
            ]
        },
        "active": True
    },
    {
        "name": "Pattern 7",
        "description": "exact X red where X in [3-8] (dynamic)",
        "type": "dynamic",
        "treat_yellow_as_green": True,
        "dynamic_values": [3, 4, 5, 6, 7, 8],
        "trigger": {
            "steps": [
                {"colors": ["red"], "operator": "exact", "count": "$X"}
            ]
        },
        "miss": {
            "steps": [
                {"colors": ["red"], "operator": "minimum", "count": "$X+1"}
            ]
        },
        "active": True
    }
]
