#/ -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import smtplib
from email.mime.text import MIMEText
import time
import logging
from datetime import datetime
import datetime as dt
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.tools.sql import drop_view_if_exists
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import xlwt
import os
from cStringIO import StringIO

from bs4 import BeautifulSoup
from selenium import webdriver
import re
from odoo.http import request
import sys
abspath = sys.path.append(os.path.abspath('gvm/models'))
from sendmail import gvm_mail

_logger = logging.getLogger(__name__)

class GvmSign(models.Model):
    _name = "gvm.sign"
    _description = "sign"
    _order = 'num'

    name = fields.Char(string='sign',required=True)
    num = fields.Integer(string='number')

class GvmSignContent(models.Model):
    _name = "gvm.signcontent"
    _description = "signcontent"
    _order = 'create_date desc, name desc'

    user_id = fields.Many2one('res.users', string='user_id', default=lambda self: self.env.uid,store=True)
    name = fields.Char(string='name', default='New')
    color = fields.Integer('Color')
    sign_ids = fields.Integer('sign_ids',compute='_compute_sign')
    dep_ids = fields.Many2one('hr.department',string='department',compute='_compute_sign',store=True)
    job_ids = fields.Many2one('hr.job',string='job_id',compute='_compute_sign',store=True)

    writer = fields.Char(string='writer', compute='_compute_user_info')
    user_department = fields.Many2one('hr.department',string='user_department',compute='_compute_user_info')
    user_job_id = fields.Many2one('hr.job',string='user_job_id',compute='_compute_user_info')
    content = fields.Text(string='content',store=True)
    content2 = fields.Text(string='content',store=True)

    check = fields.Boolean(string='check',compute='_compute_check')
    request_check1 = fields.Many2one('hr.employee',string='request_check1',store=True)
    request_check2 = fields.Many2one('hr.employee',string='request_check2',store=True)
    request_check3 = fields.Many2one('hr.employee',string='request_check3',store=True)
    request_check4 = fields.Many2one('hr.employee',string='request_check4',store=True)
    request_check5 = fields.Many2one('hr.employee',string='request_check5',store=True)
    request_check6 = fields.Many2one('hr.employee',string='request_check6',store=True)
    check1 = fields.Many2one('res.users',string='check1',store=True)
    check2 = fields.Many2one('res.users',string='check2',store=True)
    check3 = fields.Many2one('res.users',string='check3',store=True)
    check4 = fields.Many2one('res.users',string='check4',store=True)
    check5 = fields.Many2one('res.users',string='check5',store=True)
    check6 = fields.Many2one('res.users',string='check6',store=True)
    check1_date = fields.Datetime('check1_date')
    check2_date = fields.Datetime('check2_date')
    check3_date = fields.Datetime('check3_date')
    check4_date = fields.Datetime('check4_date')
    check5_date = fields.Datetime('check5_date')
    check6_date = fields.Datetime('check6_date')
    reference = fields.Many2many('hr.employee',string='참조')

    my_doc_count = fields.Integer('my_doc', compute='_compute_my_check_count')
    my_check_count = fields.Integer('my_check', compute='_compute_my_check_count')
    my_ref_count = fields.Integer('my_ref', compute='_compute_my_check_count')
    create_date = fields.Date('create_date',default=fields.Datetime.now)
    #sh
    #달력외 표시 금지
    date_from = fields.Date('start',required=True, default=fields.Datetime.now)
    date_to = fields.Date('end', default=fields.Datetime.now)
    project = fields.Many2one('project.project',string='name')
    sign = fields.Many2one('gvm.sign', string='sign',required=True)
    cost = fields.One2many('gvm.signcontent.cost','sign', string='cost')
    cost2 = fields.One2many('gvm.signcontent.cost2','sign', string='cost2')
    work = fields.One2many('gvm.signcontent.work','sign', string='work')
    timesheet = fields.Many2many('account.analytic.line','sign','timesheet',domain="[('user_id','=',uid)]",store=True,compute='_onchange_timesheet')
    reason = fields.Text('reason')
    rest1 = fields.Selection([('day','연차'),
      #sh
      #오전반차 오후반차 구분
      ('half','오전반차'),
      ('half_2','오후반차'),
      ('quarter','반반차'),
      ('vacation','휴가'),
      ('refresh','리프레시 휴가'),
      ('publicvacation','공가(예비군 등)'),
      ('sick','병가'),
      ('special','출산/특별휴가'),
      ('etc','기타')])
    basic_cost = fields.Integer('basic_cost',compute='_compute_basic_cost')
    had_cost = fields.Integer('had_cost')
    finally_cost = fields.Integer('finally_cost',compute='_compute_finally_cost')
    currency_yuan = fields.Float(string='yuan',default=171.73)
    currency_dong = fields.Float(string='dong',default=0.05)
    currency_dollar = fields.Float(string='dollar',default=1079.5)
    attachment = fields.Many2many('ir.attachment', domain="[('res_model','=','gvm.signcontent')]", string='도면')
    relate_sign = fields.Many2one('gvm.signcontent','sign')
    sign_line = fields.One2many('gvm.signcontent.line','sign','sign_line')

    check_all = fields.Boolean('전결')
    next_check = fields.Char(string='next_check',compute='_compute_next_check',store=True)
    state = fields.Selection([
        ('temp', '임시저장'),
        ('write', '상신'),
        ('check1', '검토'),
        ('check2', '결재'),
        ('check3', '결재'),
        ('check4', '결재'),
        ('check5', '결재'),
        ('done', '결재완료'),
        ('cancel', '반려'),
        ('remove', '취소')
        ], string='Status', readonly=True, index=True, copy=False, default='temp', track_visibility='onchange')
    holiday_count = fields.Char('holiday_count', compute='_compute_holiday_count')
    confirm_date = fields.Date('confirm_date')

    #sh
    #외근계획서
    #외근목적
    out_of_work_purpose = fields.Selection([
            ('meeting','미팅'),
            ('education','교육'),
            ('exposition', '박람회'),
            ('etc','기타(주요업무란에 상세기재)')])
    #외근장소
    out_of_work_area = fields.Char(string='out_of_work_area')
    #외근동행자
    out_of_work_companion = fields.Char(string='out_of_work_companion')
    #이동수단
    out_of_work_transport = fields.Selection([
    	('car','자가용'),
	('publictransport','대중교통'),
       	('taxi','택시'),
	('companycar','법인차량')])
    out_of_work_content = fields.Text(string='content',store=True)
    out_of_work_content2 = fields.Text(string='content2',store=True)
    out_of_work_date_to = fields.Datetime(default = datetime.today())
    out_of_work_date_from = fields.Datetime(default = datetime.today())
	
    @api.depends('date_from','date_to','job_ids')
    def _compute_basic_cost(self):
        for record in self:
         if record.date_to and record.date_from:
           fmt = '%Y-%m-%d'
           d1 = datetime.strptime(record.date_to,fmt)
           d2 = datetime.strptime(record.date_from,fmt)
           dayDiff = str((d1-d2).days+1)
           job_id = record.job_ids.no_of_hired_employee
           record.basic_cost = 0
	   
    @api.depends('basic_cost','had_cost','cost')
    def _compute_finally_cost(self):
        for record in self:
         user_cost = 0
         if record.cost:
          for scost in record.cost:
           if scost.card == 'personal':
            calcost = scost.cost
            if scost.currency == 'dong':
              calcost = scost.cost * record.currency_dong
            elif scost.currency == 'yuan':
              calcost = scost.cost * record.currency_yuan
            elif scost.currency == 'dollar':
              calcost = scost.cost * record.currency_dollar
            user_cost += calcost
         final_cost = round((record.had_cost - record.basic_cost - user_cost +5)/100)*100
         record.finally_cost = final_cost

    def kb_parse(self,get_currency,get_date):
      driver = webdriver.PhantomJS(executable_path="/usr/phantomjs-2.1.1-linux-x86_64/bin/phantomjs",service_log_path='/usr/lib/python2.7/dist-packages/odoo/ghostdriver.log')
      url = 'https://okbfex.kbstar.com/quics?page=C015690#CP'
      driver.get(url)

      d1 = datetime.strptime(get_date,'%Y-%m-%d')
      date = str((d1 + dt.timedelta(days=1)).date())
      driver.execute_script("uf_yesterday('"+ date +"')")
      time.sleep(1)
      html = driver.page_source
      driver.quit()
      soup = BeautifulSoup(html,'lxml')
      list_p = soup.find('div',{'class':'btnTable'})

      currency_list = []
      for gc in get_currency:
       if list_p.select('a'):
        currency_list.append(re.sub('[^0-9.]','',list_p.select('a')[gc].parent.parent.select('td')[4].text))
       else:
        return self.kb_parse(get_currency,str((d1 - dt.timedelta(days=1)).date()))
      return currency_list

    @api.onchange('date_from')
    def _onchange_currency(self):
      if self.date_from and self.sign_ids == 3:
       set_currency = [0,9,36]
       currency_list = self.kb_parse(set_currency,self.date_from)
       self.currency_dollar = currency_list[0]
       self.currency_yuan = currency_list[1]
       self.currency_dong = float(currency_list[2])/100

    @api.depends('sign')
    def _compute_sign(self):
        for record in self:
           record.dep_ids = self.env['hr.employee'].search([('user_id','=',self.env.uid)]).department_id.id
           record.job_ids = self.env['hr.employee'].search([('user_id','=',self.env.uid)]).job_id.id
           record.sign_ids = record.sign.num
    @api.model
    def _compute_user_info(self):
        for record in self:
           record.user_job_id = self.env['hr.employee'].search([('user_id','=',self.env.uid)]).job_id.id
           record.user_department = self.env['hr.employee'].search([('user_id','=',self.env.uid)]).department_id.id
           record.writer = record.user_id.name
    @api.model
    def _compute_check(self):
        for record in self:
          if self._check_name() and self._check_me():
            record.check = True
    @api.depends('state')
    def _compute_next_check(self):
      index = ['request_check1','request_check2','request_check3','request_check4','request_check5','request_check6']
      for record in self:
        if record.state == 'cancel':
	  #sh
	  #현재 서버 페이지의 정보를 가져온다.
	  rest1 = record.rest1
	  date_to = record.date_to
	  date_from = record.date_from
	  #연차의 갯수를 상신 전상태로 돌린다.
	  count = self.check_holiday_count(rest1,date_to,date_from)
	  hr_name = self.env['hr.employee'].search([('name','=',record.user_id.name)])
	  h_count = float(hr_name.holiday_count) +  float(count)
	  hr_name.write({
	            'holiday_count': h_count
	  })
	  #다음 결제권한을  작성자에게 넘긴다. 
	  record.next_check = record.writer
	  return False

        for i in index:
	  if record[i]:
            record.next_check = record[i].name
	    break

    @api.depends('user_id')
    def _compute_holiday_count(self):
      for record in self:
	hr_name = self.env['hr.employee'].search([('name','=',self.user_id.name)])
        record.holiday_count = hr_name.holiday_count

    @api.model
    def _compute_my_check_count(self):
      my_doc = self.env['gvm.signcontent'].search([('user_id','=',self.env.uid)])
      my_check_doc = self.env['gvm.signcontent'].search(['|','|','|','|','|',
                                     ('check1','=',self.env.uid),
                                     ('check2','=',self.env.uid),
                                     ('check3','=',self.env.uid),
                                     ('check4','=',self.env.uid),
                                     ('check5','=',self.env.uid),
                                     ('check6','=',self.env.uid)
				     ])
      my_check_finish_doc = self.env['gvm.signcontent'].search([('check1','=',self.env.uid)])
      my_check_deny_doc = self.env['gvm.signcontent'].search([('check1','=',self.env.uid)])
      my_ref_doc = self.env['gvm.signcontent'].search([('reference','=',self.env.uid)])
      for record in self:
        record.my_doc_count = len(my_doc)
        record.my_check_count = len(my_check_doc)
        record.my_ref_count = len(my_ref_doc)

    @api.onchange('sign_ids')
    def _default_check1(self):
        for record in self:
          user = self.env.uid
          dep = self.env['hr.department'].search([('member_ids.user_id','=',user)],limit=1)
          boss = dep.manager_id.id
          manager = self.env['hr.employee'].search([('department_id','=',10)])
          ceo = self.env['hr.employee'].search([('id','=',126)])
          if record.sign_ids in [2,3]:
            record.request_check3 = boss
            record.request_check4 = manager[1].id
            record.request_check5 = manager[0].id
          elif record.sign_ids == 5:
            record.request_check3 = boss
            record.request_check5 = manager[2].id
	  elif record.sign_ids == 6:
	    record.request_check2 = boss
	    record.request_check3 = ceo
            record.request_check4 = manager[1].id
            record.request_check5 = manager[0].id
          else:
            record.request_check1 = False
            record.request_check2 = False
            record.request_check3 = boss
            record.request_check4 = False
            record.request_check5 = False
	    record.reference = False

    @api.depends('date_from','date_to')
    def _onchange_timesheet(self):
      for record in self:
        if record.sign_ids == 2:
	 #작성한 기간동안 검색을 위해서 삭제 //(하루전날로 체크해야했음)
         worktime = self.env['account.analytic.line'].search([('date_from','>=',record.date_from),('date_to','<=',record.date_to),('user_id','=',record.user_id.id)])  #,('unit_amount','>=',1)])
         record.timesheet = worktime

    @api.model
    def _check_name(self):
        for record in self:
          if record.name != self.env.user.name and record.check1.id != self.env.uid and record.check2.id != self.env.uid and record.check3.id != self.env.uid and record.check4.id != self.env.uid and record.check5.id != self.env.uid and record.check6.id != self.env.uid:return True

    @api.model
    def _check_me(self):
        for record in self:
          if record.next_check == self.env.user.name :return True
    @api.model
    def _check_high_job_id(self):
        for record in self:
          if record.user_job_id.no_of_hired_employee >= 4 and record.job_ids.no_of_hired_employee < record.user_job_id.no_of_hired_employee:return True

    @api.multi
    def button_check_all(self):
        self.sudo(self.user_id.id).write({'state':'done', 'check3': self.env.uid, 'next_check':self.request_check4.id or 'done', 'check3_date': datetime.now()})
	return {}
    @api.multi
    def button_reorder(self):
        sign = self.env['gvm.signcontent'].search([('id','=',self.id)])
	check1,check2,check3,check4,check5 = 0,0,0,0,0
	if sign.check1:
          check1 = self.env['hr.employee'].search([('user_id','=',sign.check1.id)]).id
	if sign.check2:
          check2 = self.env['hr.employee'].search([('user_id','=',sign.check2.id)]).id
	if sign.check3:
          check3 = self.env['hr.employee'].search([('user_id','=',sign.check3.id)]).id
	if sign.check4:
          check4 = self.env['hr.employee'].search([('user_id','=',sign.check4.id)]).id
	if sign.check5:
          check5 = self.env['hr.employee'].search([('user_id','=',sign.check5.id)]).id
	_logger.warning(check1)
        self.sudo(self.user_id.id).write({'state': 'write',
	                                  'check1':False,
					  'check2':False,
					  'check3':False,
					  'check4':False,
					  'check5':False,
					  'reason':False,
	                                  'check1_date':False,
	                                  'check2_date':False,
	                                  'check3_date':False,
	                                  'check4_date':False,
	                                  'check5_date':False,
					  'request_check1':check1 or self.request_check1.id,
					  'request_check2':check2 or self.request_check2.id,
					  'request_check3':check3 or self.request_check3.id,
					  'request_check4':check4 or self.request_check4.id,
					  'request_check5':check5 or self.request_check5.id,
					  'next_check':self.check1.name})
        #sh
	#근태신청서
        if self.sign.num == 1:
	 #현재 연차 갯수
         count = self.check_holiday_count()
	 #로그인 유저 정보
         hr_name = self.env['hr.employee'].sudo(1).search([('name','=',self.user_id.name)])
	 #총 연차갯수 - 사용한 연차 갯수
         h_count = float(hr_name.holiday_count) - float(count)
	 #적용
         hr_name.holiday_count = float(h_count)
        return {}

    @api.multi
    def sign_view(self):
        uname = self.env['hr.employee'].search([('user_id','=',self.env.uid)]).id
        username = self.env['hr.employee'].search([('user_id','=',self.env.uid)]).name
        domain = [('next_check','=',username),('state','not in',['temp','done','cancel'])]
        return {
            'name': _('Sign'),
            'domain': domain,
            'res_model': 'gvm.signcontent',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'limit': 80,
            'context': "{}"
        }

    @api.multi
    def sign_reference_view(self):
        uname = self.env['hr.employee'].search([('user_id','=',self.env.uid)]).id
        username = self.env['hr.employee'].search([('user_id','=',self.env.uid)]).name
        domain = [('reference','in',uname)]
        return {
            'name': _('Sign'),
            'domain': domain,
            'res_model': 'gvm.signcontent',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'limit': 80,
            'context': "{}"
        }
    #sh
    def return_holiday_count(self):
         #근태신청서
	 if self.sign.num == 1:
	  #연차갯수
	  count = self.check_holiday_count()
	  #로그인한 유저정보
	  hr_name = self.env['hr.employee'].sudo(1).search(['&',('name','=',self.user_id.name),('department_id','=',self.user_department.id)])
	  #총 연차갯수 + 사용했던 연차갯수
	  h_count = float(hr_name.holiday_count) + float(count)
	  # 적용
	  hr_name.holiday_count = float(h_count)


    #sh
    #취소버튼
    def button_remove(self):
	#근태신청서
    	if self.sign.num == 1:
	 #연차갯수
	 count = self.check_holiday_count()
	 #로그인한 유저정보
	 hr_name = self.env['hr.employee'].sudo(1).search(['&',('name','=',self.user_id.name),('department_id','=',self.user_department.id)])
	 #총 연차갯수 + 사용했던 연차갯수
	 h_count = float(hr_name.holiday_count) + float(count)
	 # 적용
         hr_name.holiday_count = float(h_count)
	 #상태 정보: 취소상태
         self.write({'state':'remove'})
	
	elif self.sign.num == 3:
	 #상태 정보: 취소상태
	 self.write({'state':'remove'})

    @api.multi
    def button_confirm(self):
	check_name = ''
	if self.request_check1:
	 check_name = self.request_check1.name
	elif self.request_check3:
	 check_name = self.request_check3.name
	self.write({'next_check':check_name,
	    	    'state':'write',
		    'confirm_date':datetime.today()
	})
	if self.sign.num == 1:
	  count = self.check_holiday_count()
	  hr_name = self.env['hr.employee'].sudo(1).search([('name','=',self.user_id.name)])
	  h_count = float(hr_name.holiday_count) - float(count)
	  _logger.warning(h_count)

	  if h_count < -7:
           raise UserError(_('사용 가능한 연차 개수를 초과하셨습니다.'))
	  hr_name.holiday_count = float(h_count)
	  _logger.warning(hr_name.holiday_count)

        a = gvm_mail()
	model_name = 'gvm.signcontent'
	postId = self.id
        po_num = self.env[model_name].search([('id','=',postId)]).name

	receivers = []
        check1 = self.request_check1.id
        check2 = self.request_check2.id
        check3 = self.request_check3.id
        we = self.env['hr.employee'].search([('id','in',(check1,check2,check3))])
        menu_id = "320"
	action_id = ""
        for person in we:
          receivers.append(person)
	a.gvm_send_mail(self.env.user.name, receivers, '결재문서', postId, po_num, model_name, menu_id, action_id)


    def check_holiday_count(self, rest1=None, date_to=None, date_from=None):
        count = 0
	#반려를 클릭한 경우
	if rest1 != None:
	   rest = rest1
	   date_to = date_to
	   date_from = date_from
	#반려를 클릭하지 않은경우
	else:
	   rest = self.rest1
	   date_to = self.date_to
	   date_from = self.date_from

	if rest in ['refresh','publicvacation','special']:
	  return count
	#sh 
	#오전반차 오후반차 구분  
	if rest == 'half':
	  count = 0.5
	  return count
	elif rest == 'half_2':
	  count = 0.5
	  return count
	elif rest == 'quarter':
	  count = 0.25
	  return count
	#연차일경우 갯수 파악  
        fmt = '%Y-%m-%d'
        d1 = datetime.strptime(date_to,fmt)
        d2 = datetime.strptime(date_from,fmt)
        count = (d1-d2).days+1
	return count

    @api.model
    def create(self, vals):
        if vals.get('name','New') == 'New':
           vals['name'] = self.env['ir.sequence'].next_by_code('gvm.sign.number') or '/'
        res = super(GvmSignContent, self).create(vals)
	return res

    @api.multi
    def unlink(self):        
        for record in self:
            if not record.user_id.name == self.env.user.name:
                raise UserError(_('본인 외 삭제 불가'))
	    else:
	      #sh
	      #삭제되었을경우 연차 갯수 복귀
	      #근태신청서
	      if self.sign.num == 1:
	        #연차갯수
	        count = self.check_holiday_count()
	        #로그인한 유저정보
	        hr_name = self.env['hr.employee'].sudo(1).search(['&',('name','=',self.user_id.name),('department_id','=',self.user_department.id)])
	        #총 연차갯수 + 사용했던 연차갯수
	        h_count = float(hr_name.holiday_count) + float(count)
	        # 적용
	        hr_name.holiday_count = float(h_count)
        return super(GvmSignContent, self).unlink()

    @api.multi
    def write(self, vals):
        allower = [1,168,294]
        for record in self:
            if record.state in ['temp','write','cancel']:
	     if self.env.user.name != record.user_id.name and self.env.uid != 1:
               raise UserError(_('본인 외 수정 불가'))
            else:
             if self.env.uid not in allower:
                raise UserError(_('이미 결재가 진행 중인 문서는 수정이 불가합니다.'))
        return super(GvmSignContent, self).write(vals)


class GvmSignContentCost(models.Model):
    _name = "gvm.signcontent.cost"
    _description = "signcontent cost"
    _order = 'create_date, date'

    name = fields.Char(string='name',required=True)
    date = fields.Date(string='date')
    sign = fields.Many2one('gvm.signcontent','sign')
    cost = fields.Integer('cost')
    currency_id = fields.Many2one('res.currency',string='Currency')
    currency = fields.Selection([('won','원'),('dong','동'),('yuan','위안'),('dollar','달러'),('etc','기타')],default='won',string='화폐')
    description = fields.Char(string='description')
    ratio = fields.Float('환율',default='1')
    card = fields.Selection([('personal','개인'),('corporation','법인')],default='personal')

class GvmSignContentCost2(models.Model):
    _name = "gvm.signcontent.cost2"
    _description = "signcontent cost2"
    _order = 'create_date, date'

    name = fields.Char(string='name',required=True)
    date = fields.Date(string='date')
    sign = fields.Many2one('gvm.signcontent','sign')
    cost = fields.Integer('cost')
    currency_id = fields.Many2one('res.currency',string='Currency')
    currency = fields.Selection([('won','원'),('dong','동'),('yuan','위안'),('dollar','달러'),('etc','기타')],default='won',string='화폐')
    description = fields.Char(string='description')
    ratio = fields.Float('환율',default='1')
    card = fields.Selection([('personal','개인'),('corporation','법인')],default='personal')

class GvmSignContentWork(models.Model):
    _name = "gvm.signcontent.work"
    _description = "signcontent work"
    _order = 'create_date, date'

    name = fields.Char(string='name',required=True)
    date_from = fields.Date(string='datefrom')
    date_to = fields.Date(string='dateto')
    sign = fields.Many2one('gvm.signcontent','sign')
    timesheet = fields.Many2one('account.analytic.line','timesheet')
    
class GvmSignLine(models.Model):
    _name = "gvm.signcontent.line"
    _order = ''

    name = fields.Many2one ( ' hr.employee ' ,string = ' name ' )
    sequence = fields.Integer ( ' 순번 ' )
    state = fields.Selection ([( ' sign ' , ' 결재 ' ), ( ' 2 ' , ' 합의 ' ), ( ' 3 ' , ' 참조 ' ), ( ' 4 ' , ' 열람 ' )])
    sign = fields.Many2one ( ' gvm.signcontent ' , ' sign ' )


