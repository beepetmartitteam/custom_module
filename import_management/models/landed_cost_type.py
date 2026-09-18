# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LandedCostType(models.Model):
    _name = 'landed.cost.type'
    _description = 'Landed Cost Type'
    _order = 'sequence, name'

    name = fields.Char(
        string='Cost Type',
        required=True,
        translate=True,
    )
    
    code = fields.Char(
        string='Code',
        required=True,
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    
    description = fields.Text(
        string='Description',
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
