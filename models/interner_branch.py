# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

from datetime import date
from datetime import datetime
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import calendar
import re
import json
from dateutil.relativedelta import relativedelta
import qrcode
from PIL import Image
from random import choice
from string import digits



class InterBranchTransfer(models.Model):
    _name = 'inter.branch.transfer'


    name = fields.Char("Name", index=True, default=lambda self: _('New'))
    sequence = fields.Integer(index=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done'),('invoice', 'Invoiced'), ('cancelled', 'Cancelled')], readonly=True,
                             default='draft', copy=False, string="Status")
    inter_company_lines = fields.One2many('inter.branch.transfer.line','inter_id')
    company_id = fields.Many2one('res.company',string='Company Name')
    from_branch = fields.Many2one('company.branches', string='From Branch')
    to_branch = fields.Many2one('company.branches', string='To Branch')

    picking_type_id = fields.Many2one('stock.picking.type')
    location_id = fields.Many2one('stock.location',string='Source Location')
    dest_location_id = fields.Many2one('stock.location',string='Dest Location')
    partner_id = fields.Many2one('res.partner',string='Partner')
    invoice_id = fields.Many2one('account.move',string='Invoice')




    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(
                    'inter.branch.transfer') or _('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('inter.branch.transfer') or _('New')
        return super(InterBranchTransfer, self).create(vals)

    @api.onchange('from_branch')
    def onchange_from_branch(self):
        if self.from_branch:
            self.location_id = self.env['stock.location'].search([('branch_id','=',self.from_branch.id),('company_id','=',self.company_id.id)])

            # return {'domain': {'location_id': [('id', 'in', locations.ids)]}}
    @api.onchange('to_branch')
    def onchange_to_branch(self):
        if self.to_branch:
            self.dest_location_id = self.env['stock.location'].search([('branch_id','=',self.to_branch.id),('company_id','=',self.company_id.id)])

            # return {'domain': {'location_id': [('id', 'in', locations.ids)]}}

    @api.onchange('company_id')
    def onchange_company_ids(self):
        if self.company_id:
            self.partner_id = self.company_id.partner_id
            branches = self.env['company.branches'].search([('company_id','=',self.company_id.id)])
            return {'domain': {'from_branch': [('id', 'in', branches.ids)],
                               'to_branch': [('id', 'in', branches.ids)],
                               }}

    # @api.onchange('company_id')
    # def onchange_company_id(self):
    #     if self.company_id:
    #         to_locations = self.env['stock.location'].search([('company_id','=',self.to_company.id)])
    #         return {'domain': {'dest_location_id': [('id', 'in', to_locations.ids)]}}

    def send_other_location(self):
        picking_type_id  = self.env['stock.picking.type'].sudo().search([('warehouse_id.company_id','=',self.company_id.id),('code','=','internal')])
        pick = self.env['stock.picking'].sudo().create({
            'picking_type_id': picking_type_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.dest_location_id.id,
            'origin': self.name,
        })
        for line in self.inter_company_lines:

            trans_product_line = self.env['stock.move'].create({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                # 'product_uom_qty': line.quantity_done,
                'product_uom_qty': line.transfer_qty,
                'product_uom': line.product_id.uom_id.id,
                'quantity_done': line.transfer_qty,
                'location_id': self.location_id.id,
                'location_dest_id': self.dest_location_id.id,
                'picking_type_id': picking_type_id.id,
                'picking_id': pick.id
            })
            pick.sudo().action_confirm()
            pick.sudo().action_assign()
            m = pick.button_validate()
            pick.sudo()._action_done()
        self.write({'state':'done'})

    def action_create_invoice(self):
        journal_id = self.env['account.journal'].sudo().search(
            [('name', '=', 'Tax Invoices'), ('type', '=', 'sale'),('company_id', '=', self.company_id.id)]).id,
        account_id = self.env['account.account'].search([('name', '=', 'Local Sales'),('company_id', '=', self.company_id.id)])
        account_ids = self.env['account.account'].search([('name', '=', 'Debtors'),('company_id', '=', self.company_id.id)])
        list = []
        for line in self.inter_company_lines:
            dict =(0, 0, {
                'name': line.product_id.name,
                # 'origin': self.name,
                'account_id': account_id.id,
                'price_unit': line.price_unit,
                'quantity': line.transfer_qty,
                'discount': 0.0,
                'product_uom_id': line.product_id.uom_id.id,
                'product_id': line.product_id.id,
                # 'sale_line_ids': [(6, 0, [line.id for line in sale_order.order_line])],
            })
            list.append(dict)

        invoice = self.env['account.move'].sudo().create({
            'partner_id': self.partner_id.id,
            # 'currency_id': self.currency_id.id,
            'move_type': 'out_invoice',
            'state':'draft',
            'company_id':self.company_id.id,
            'invoice_date': datetime.today().date(),
            'journal_id':journal_id,
            'l10n_in_gst_treatment':'unregistered',
            # 'account_id': account_ids.id,
            'invoice_line_ids':list,
            'transfer_id':self.id,
            'branch_id':self.from_branch.id,

        })
        invoice.action_post()
        self.invoice_id = invoice

        self.write({'state':'invoice'})

class InterBranchTransferLine(models.Model):
    _name = 'inter.branch.transfer.line'

    inter_id = fields.Many2one('inter.branch.transfer')
    product_id = fields.Many2one('product.product',string='Product')
    uom_id = fields.Many2one('uom.uom', 'Unit of measure')
    transfer_qty = fields.Float(string='Transfer Qty')
    price_unit = fields.Float(string='Price Unit')

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id



class Location(models.Model):
    _inherit = "stock.location"

    branch_id = fields.Many2one('company.branches', string='Branch Name')


    @api.onchange('company_id')
    def onchange_company_ids(self):
        if self.company_id:
            return {'domain': {'branch_id': [('id', 'in', self.env['company.branches'].search([('company_id','=',self.company_id.id)]).ids)]}}


class AccountMove(models.Model):
    _inherit = "account.move"

    transfer_id = fields.Many2one('inter.branch.transfer')