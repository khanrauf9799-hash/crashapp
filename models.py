import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum
import json

db = SQLAlchemy()

class Round(db.Model):
    __tablename__ = 'rounds'
    
    id = db.Column(db.Integer, primary_key=True)
    round_number = db.Column(db.String(50), unique=True, nullable=False)
    crash_value = db.Column(db.Float, nullable=False)
    color = db.Column(db.String(10), nullable=False)
    source = db.Column(db.String(50), default='bc.game')
    game_id = db.Column(db.String(100))
    max_rate = db.Column(db.Float)
    total_bet_amount = db.Column(db.Float)
    total_win_amount = db.Column(db.Float)
    total_profit_amount = db.Column(db.Float)
    player_count = db.Column(db.Integer)
    bet_count = db.Column(db.Integer)
    hash_value = db.Column(db.String(200))
    game_timestamp = db.Column(db.String(100))
    raw_payload = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'round_number': self.round_number,
            'crash_value': self.crash_value,
            'color': self.color,
            'source': self.source,
            'game_id': self.game_id,
            'max_rate': self.max_rate,
            'total_bet_amount': self.total_bet_amount,
            'total_win_amount': self.total_win_amount,
            'total_profit_amount': self.total_profit_amount,
            'player_count': self.player_count,
            'bet_count': self.bet_count,
            'hash_value': self.hash_value,
            'timestamp': self.game_timestamp,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Pattern(db.Model):
    __tablename__ = 'patterns'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    pattern_type = db.Column(db.String(20), default='static')
    rule_json = db.Column(db.Text, nullable=False)
    active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    stats = db.relationship('PatternStats', backref='pattern', uselist=False, cascade='all, delete-orphan')
    
    def to_dict(self):
        rule = json.loads(self.rule_json) if self.rule_json else {}
        stats_dict = self.stats.to_dict() if self.stats else {}
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'pattern_type': self.pattern_type,
            'rule_json': rule,
            'active': self.active,
            'priority': self.priority,
            'stats': stats_dict,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class PatternStats(db.Model):
    __tablename__ = 'pattern_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    pattern_id = db.Column(db.Integer, db.ForeignKey('patterns.id'), nullable=False)
    trigger_streak = db.Column(db.Integer, default=0)
    miss_streak = db.Column(db.Integer, default=0)
    total_triggers = db.Column(db.Integer, default=0)
    total_misses = db.Column(db.Integer, default=0)
    longest_trigger_streak = db.Column(db.Integer, default=0)
    longest_miss_streak = db.Column(db.Integer, default=0)
    alert_cooldown_rounds = db.Column(db.Integer, default=0)
    last_alert_round = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'trigger_streak': self.trigger_streak,
            'miss_streak': self.miss_streak,
            'total_triggers': self.total_triggers,
            'total_misses': self.total_misses,
            'longest_trigger_streak': self.longest_trigger_streak,
            'longest_miss_streak': self.longest_miss_streak,
            'alert_cooldown_rounds': self.alert_cooldown_rounds
        }


class PatternSubStats(db.Model):
    __tablename__ = 'pattern_sub_stats'

    id = db.Column(db.Integer, primary_key=True)
    pattern_id = db.Column(db.Integer, db.ForeignKey('patterns.id'), nullable=False)
    sub_pattern_key = db.Column(db.String(50), nullable=False)
    trigger_streak = db.Column(db.Integer, default=0)
    miss_streak = db.Column(db.Integer, default=0)
    total_triggers = db.Column(db.Integer, default=0)
    total_misses = db.Column(db.Integer, default=0)
    longest_trigger_streak = db.Column(db.Integer, default=0)
    longest_miss_streak = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('pattern_id', 'sub_pattern_key', name='uq_pattern_sub_stats_pattern_key'),
    )

    pattern = db.relationship('Pattern', backref='sub_stats')

    def to_dict(self):
        return {
            'pattern_id': self.pattern_id,
            'sub_pattern_key': self.sub_pattern_key,
            'trigger_streak': self.trigger_streak,
            'miss_streak': self.miss_streak,
            'total_triggers': self.total_triggers,
            'total_misses': self.total_misses,
            'longest_trigger_streak': self.longest_trigger_streak,
            'longest_miss_streak': self.longest_miss_streak,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class StreakHistory(db.Model):
    __tablename__ = 'streak_history'
    
    id = db.Column(db.Integer, primary_key=True)
    pattern_id = db.Column(db.Integer, db.ForeignKey('patterns.id'), nullable=False)
    streak_type = db.Column(db.String(10), nullable=False)
    streak_length = db.Column(db.Integer, nullable=False)
    sub_pattern_key = db.Column(db.String(50))
    start_round = db.Column(db.String(50))
    end_round = db.Column(db.String(50))
    sequence_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    pattern = db.relationship('Pattern', backref='streak_histories')
    
    def to_dict(self):
        return {
            'id': self.id,
            'pattern_id': self.pattern_id,
            'pattern_name': self.pattern.name if self.pattern else None,
            'streak_type': self.streak_type,
            'streak_length': self.streak_length,
            'sub_pattern_key': self.sub_pattern_key,
            'start_round': self.start_round,
            'end_round': self.end_round,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    pattern_id = db.Column(db.Integer, db.ForeignKey('patterns.id'), nullable=False)
    alert_type = db.Column(db.String(20), nullable=False)
    payload = db.Column(db.Text)
    status = db.Column(db.String(20), default='sent')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    pattern = db.relationship('Pattern', backref='alerts')
    
    def to_dict(self):
        return {
            'id': self.id,
            'pattern_id': self.pattern_id,
            'pattern_name': self.pattern.name if self.pattern else None,
            'alert_type': self.alert_type,
            'payload': json.loads(self.payload) if self.payload else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ColorConfig(db.Model):
    __tablename__ = 'color_config'
    
    id = db.Column(db.Integer, primary_key=True)
    red_max = db.Column(db.Float, default=2.0)
    green_max = db.Column(db.Float, default=10.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'red_max': self.red_max,
            'green_max': self.green_max,
            'rules': {
                'red': f'value < {self.red_max}',
                'green': f'{self.red_max} <= value < {self.green_max}',
                'yellow': f'value >= {self.green_max}'
            }
        }

class NotificationSettings(db.Model):
    __tablename__ = 'notification_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    telegram_token = db.Column(db.String(200))
    telegram_chat_id = db.Column(db.String(100))
    webhook_url = db.Column(db.String(500))
    email_smtp_host = db.Column(db.String(200))
    email_smtp_port = db.Column(db.Integer, default=587)
    email_username = db.Column(db.String(200))
    email_password = db.Column(db.String(200))
    email_to = db.Column(db.String(500))
    enabled_channels = db.Column(db.Text, default='["websocket"]')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'telegram_enabled': bool(self.telegram_token and self.telegram_chat_id),
            'webhook_enabled': bool(self.webhook_url),
            'email_enabled': bool(self.email_smtp_host and self.email_to),
            'enabled_channels': json.loads(self.enabled_channels) if self.enabled_channels else ['websocket']
        }

_color_config_cache = None

def get_color_config():
    global _color_config_cache
    if _color_config_cache is None:
        config = ColorConfig.query.first()
        if config:
            _color_config_cache = (config.red_max, config.green_max)
        else:
            _color_config_cache = (2.0, 10.0)
    return _color_config_cache

def invalidate_color_config_cache():
    global _color_config_cache
    _color_config_cache = None

def get_color_from_value(value):
    red_max, green_max = get_color_config()
    if value < red_max:
        return 'red'
    elif value < green_max:
        return 'green'
    else:
        return 'yellow'
