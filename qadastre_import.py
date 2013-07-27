# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Qadastre - import main methods
                                 A QGIS plugin
 This plugins helps users to import the french land registry ('cadastre') 
 into a database. It is meant to ease the use of the data in QGIs 
 by providing search tools and appropriate layer symbology.
                              -------------------
        begin                : 2013-06-11
        copyright            : (C) 2013 by 3liz
        email                : info@3liz.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import sys, os
import re
import time
import tempfile
import shutil
from distutils import dir_util
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *

# db_manager scripts
from db_manager.db_plugins.plugin import DBPlugin, Schema, Table, BaseError
from db_manager.db_plugins import createDbPlugin
from db_manager.dlg_db_error import DlgDbError
       



class qadastreImport(QObject):

    def __init__(self, dialog):
        self.dialog = dialog
        
        self.connector = self.dialog.db.connector    
        self.scriptSourceDir = os.path.join(self.dialog.plugin_dir, "scripts/opencadastre/trunk/data/pgsql")
        self.scriptDir = tempfile.mkdtemp()
        self.edigeoDir = tempfile.mkdtemp()
        self.majicDir = tempfile.mkdtemp()
        self.replaceDict = {
            '[PREFIXE]': '"%s".' % self.dialog.schema, 
            '[VERSION]': self.dialog.dataVersion,
            '[ANNEE]': self.dialog.dataYear,
            '[FICHIER_BATI]': self.dialog.majicSourceFileNames['bati'],
            '[FICHIER_FANTOIR]': self.dialog.majicSourceFileNames['fantoir'],
            '[FICHIER_LOTLOCAL]': self.dialog.majicSourceFileNames['lotlocal'],
            '[FICHIER_NBATI]': self.dialog.majicSourceFileNames['nbati'],
            '[FICHIER_PDL]': self.dialog.majicSourceFileNames['pdl'],
            '[FICHIER_PROP]': self.dialog.majicSourceFileNames['prop']
        }
        self.go = True
        
        # copy opencadastre script files to temporary dir
        self.copyFilesToTemp(self.scriptSourceDir, self.scriptDir)


    def installOpencadastreStructure(self):
        '''
        Create the empty db structure
        '''        
        # install opencadastre structure
        self.executeSqlScript('create_metier.sql')
        self.executeSqlScript('create_constraints.sql')
        self.executeSqlScript('insert_nomenclatures.sql')
        
        return None



    def importEdigeo(self):
    
        # copy files in temp dir
        self.copyFilesToTemp(self.dialog.edigeoSourceDir, self.edigeoDir)
    
        return None
        

    def importMajic(self):
    
        
        # copy files in temp dir
        self.copyFilesToTemp(self.dialog.majicSourceDir, self.majicDir)
        
        # replace parameters
        replaceDict = self.replaceDict.copy()
        replaceDict['[CHEMIN]'] = os.path.realpath(self.majicDir) + '/'
        
        scriptList = [
            'COMMUN/suppression_constraintes.sql',
            'COMMUN/majic3_purge_donnees.sql',
            'COMMUN/majic3_import_donnees_brutes.sql',
            '%s/majic3_formatage_donnees.sql' % self.dialog.dataVersion,
            'COMMUN/creation_contraintes.sql',
            'COMMUN/majic3_purge_donnees_brutes.sql'
        ]
        for s in scriptList:
            scriptPath = os.path.join(self.scriptDir, s)
            self.replaceParametersInScript(scriptPath, replaceDict)
            self.executeSqlScript(s)
    
        return None
        

        
    #
    # TOOLS
    #


    def copyFilesToTemp(self, source, target):
        '''
        Copy opencadastre scripts
        into a temporary folder
        '''
        
        self.dialog.updateLog('Copie des fichiers de %s' % source)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        # copy script directory
        try:
            dir_util.copy_tree(source, target)
            os.chmod(target, 0777)
        except IOError, e:
            msg = u"Erreur lors de la copie des scripts d'import: %s" % e
            QMessageBox.information(self.dialog, 
            "Qadastre", msg)
            self.go = False
            return msg
    
        finally:
            QApplication.restoreOverrideCursor()
        
        return None



    def replaceParametersInScript(self, scriptPath, replaceDict):
        '''
        Replace all parameters in sql scripts
        with given values
        '''
        
        self.dialog.updateLog('Configuration du script %s' % scriptPath)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        def replfunc(match):
            return replaceDict[match.group(0)]
        regex = re.compile('|'.join(re.escape(x) for x in replaceDict))

        try:       
            fin = open(scriptPath)
            data = fin.read().decode("utf-8-sig")
            fin.close()
            fout = open(scriptPath, 'w')
            data = regex.sub(replfunc, data).encode('utf-8')
            fout.write(data)
            fout.close()
            
        except IOError, e:
            msg = u"Erreur lors du paramétrage des scripts d'import: %s" % e
            self.dialog.updateLog(msg)
            return msg
            
        finally:
            QApplication.restoreOverrideCursor()            
        
        
        return None

        
    def setSearchPath(self, sql, schema):
        '''
        Set the search_path parameters if postgis database
        '''        
        prefix = u'SET search_path = %s, public, pg_catalog;' % schema
        sql = prefix + sql

        return sql


    def executeSqlScript(self, scriptName):
        '''
        Execute an SQL script file
        from opencadastre
        '''
    
        self.dialog.updateLog('Lancement du script %s' % scriptName)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        # Read sql script
        sql = open(os.path.join(self.scriptDir, scriptName)).read()
        sql = sql.decode("utf-8-sig")
        
        # Set schema if needed
        if self.dialog.dbType == 'postgis':
            sql = self.setSearchPath(sql, self.dialog.schema)
            
        if scriptName == 'create_metier.sql':
            sup = u'''
              SET search_path = %s, public, pg_catalog;
              CREATE TABLE om_parametre (
              om_parametre serial,
              libelle character varying(20) NOT NULL,
              valeur character varying(50) NOT NULL,
              om_collectivite integer NOT NULL
              );
            ''' % self.dialog.schema
            sql = sup + sql
        
        # Execute query
        c = None
        try:
            c = self.connector._execute_and_commit(sql)

        except BaseError as e:
        
            DlgDbError.showError(e, self.dialog)
            self.dialog.updateLog(e.msg)
            return

        finally:
            QApplication.restoreOverrideCursor()
            if c:
                c.close()
                del c
    
        return None
