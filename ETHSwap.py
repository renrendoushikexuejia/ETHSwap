# 2023年5月13日21:27:17开始 写一个ETH互相转账的软件
# 左侧所有控件正常命名,右侧所有控件与左侧对应加后缀_2,右侧控件用到的函数名也是加后缀_2

import random
import sys,os,json,datetime
from PyQt5.QtWidgets import QMainWindow,QApplication,QMessageBox,QFileDialog,QInputDialog,QTreeWidgetItem,QTreeWidgetItemIterator
from PyQt5.QtCore import Qt
from web3 import Web3
from eth_account import Account
import re
import time
import pyperclip
from hdwallet import BIP44HDWallet
from hdwallet.utils import generate_mnemonic
# 生成私钥要导入对应的值,例如EthereumMainnet  BitcoinMainnet  参考https://hdwallet.readthedocs.io/en/latest/cryptocurrencies.html
from hdwallet.cryptocurrencies import EthereumMainnet       
from hdwallet.cryptocurrencies import BitcoinMainnet
from hdwallet.derivations import BIP44Derivation
from Ui_ETHSwapForm import Ui_ETHSwapForm
from keyAddForm import keyAdd
 
# 定义全局常量
gDict = {}      # 用于存储当前打开的 .km文件转换成的字典
gDict_2 = {}    # 用于存储右侧的字典

# 定义全局函数
# 数值拆分,把num拆分成n个随机数字, n个随机数字之和是num. 放在列表中返回
def split_number(num, n):
    num_int = int(num * 10**4)
    breakpoints = []
    while len(breakpoints) < n - 1:
        x = random.randint(1, num_int - 1)
        if x not in breakpoints:
            breakpoints.append(x)
    breakpoints = sorted(breakpoints)
    breakpoints = [0] + breakpoints + [num_int]
    result = [(breakpoints[i+1] - breakpoints[i]) / 10**4 for i in range(n)]
    return result

# 根据参数生成对应的私钥 公钥 地址 助记词
def generate_wallets(keyType: str, count: int):
    if keyType.lower() == 'eth/bsc':
        cryptocurrency = EthereumMainnet
    elif keyType.lower() == 'btc':
        cryptocurrency = BitcoinMainnet

    wallets = []
    for i in range(count):
        # Generate english mnemonic words
        mnemonic = generate_mnemonic(language="english", strength=128)
        # Secret passphrase/password for mnemonic
        passphrase = None
        # Initialize Ethereum 或者其它 mainnet BIP44HDWallet
        bip44_hdwallet = BIP44HDWallet(cryptocurrency=cryptocurrency)
        # Get Ethereum BIP44HDWallet from mnemonic
        bip44_hdwallet.from_mnemonic(mnemonic=mnemonic, language="english", passphrase=passphrase)
        # Clean default BIP44 derivation indexes/paths
        bip44_hdwallet.clean_derivation()
        # Derivation from Ethereum BIP44 derivation path
        bip44_derivation = BIP44Derivation(cryptocurrency=cryptocurrency, account=0, change=False, address=0)
        # Drive Ethereum BIP44HDWallet
        bip44_hdwallet.from_path(path=bip44_derivation)
        # Append wallet information to list
        wallets.append({
            "mnemonic": mnemonic,
            "private_key": bip44_hdwallet.private_key(),
            "public_key": bip44_hdwallet.public_key(),
            "address": bip44_hdwallet.address()
        })
    return wallets

# 检查字符串是否符合ETH私钥规则
def is_valid_ethereum_private_key(key: str) -> bool:
    # 检查字符串是否为十六进制
    if not re.fullmatch(r'^[0-9a-fA-F]+$', key):
        return False

    # 检查字符串长度是否为 64
    if len(key) != 64:
        return False

    return True

# 根据下拉列表框cbNetwork的内容  获得对应的Web3.HTTPProvider
def getWeb3HTTPProvider(networkName: str):
    # ["Sepolia Testnet", "Goerli Testnet", "ETH Mainnet", "BSC Mainnet", "BSC Testnet"]
    if networkName == 'Sepolia Testnet':
        w3 = Web3(Web3.HTTPProvider('https://sepolia.infura.io/v3/7c1b8b9a7f4c431ab978bcb373a9fd32'))       # sepolia测试网
    elif networkName == 'Goerli Testnet':
        w3 = Web3(Web3.HTTPProvider('https://goerli.infura.io/v3/7c1b8b9a7f4c431ab978bcb373a9fd32'))    # goerli 测试网
    elif networkName == 'ETH Mainnet':
        w3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/7c1b8b9a7f4c431ab978bcb373a9fd32'))   # ETH 主网
    elif networkName == 'BSC Mainnet':
        w3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org'))
    elif networkName == 'BSC Testnet':
        w3 = Web3(Web3.HTTPProvider('https://data-seed-prebsc-2-s1.binance.org:8545'))

    return w3


# 获得当前gas price 并更新界面
def getGasPrice(w3Provider):
    gasPrice = w3Provider.from_wei(w3Provider.eth.gas_price, 'gwei')
    return gasPrice

#  已知私钥,查询余额
def getBalance(key, w3Provider):
    address = Account.from_key(key).address
    balanceWei = w3Provider.eth.get_balance(address)
    balanceETH = w3Provider.from_wei(balanceWei, 'ether')
    return balanceETH

# 获得所选网络的chainID "BSC Mainnet", "BSC Testnet"
def getChainID(networkName: str) -> int:
    if networkName == 'Sepolia Testnet':
        chainID = 11155111
    elif networkName == 'Goerli Testnet':
        chainID = 5
    elif networkName == 'ETH Mainnet':
        chainID = 1
    elif networkName == 'BSC Mainnet':
        chainID = 56
    elif networkName == 'BSC Testnet':
        chainID = 97

    return chainID


# 转账函数,参数为 发送方私钥, 接收方私钥, 转账金额, gas price, gas limit
def transfer_eth(w3Provider, sender_private_key: str, receiver_private_key: str, chainID: int,eth_amount: float, 
                gas_price: int, gas_limit: int) -> tuple[bool, str]:
    # 获取发送方和接收方地址
    sender_address = Account.from_key(sender_private_key).address
    receiver_address = Account.from_key(receiver_private_key).address


    # tempBalance = w3.eth.get_balance(sender_address)
    # tempBalance = w3.from_wei( tempBalance, 'ether')
    # print(tempBalance)
    # print('gas_price', type(gas_price))
    # print('w3.eth.gas_price', w3.eth.gas_price)
    # 计算交易所需的gas
    if not gas_price:   # 判断gas_price为0或空
        gas_price = w3Provider.eth.gas_price
    if not gas_limit:
        gas_limit = 21000       # 发送以太币所需的标准gas数量

    value = w3Provider.to_wei(eth_amount, 'ether')
    transaction_cost = gas_price * gas_limit + value
    
    # 检查发送方余额是否充足
    sender_balance = w3Provider.eth.get_balance(sender_address)
    if sender_balance < transaction_cost:
        # print('sender_balance', sender_balance)
        # print('transaction_cost', transaction_cost)
        return False, '余额不足'
    
    # 构造交易
    nonce = w3Provider.eth.get_transaction_count(sender_address)       
    transaction = {
        'from': sender_address,
        'to': receiver_address,
        'value': value,
        'gas': gas_limit,
        'gasPrice': gas_price,
        'nonce': nonce,
        'chainId': chainID     # 区块链网络的ID
    }
    
    # print(transaction)
    # 签名交易并发送
    signed_transaction = w3Provider.eth.account.sign_transaction(transaction, sender_private_key)
    tx_hash = w3Provider.eth.send_raw_transaction(signed_transaction.rawTransaction)
    
    # 等待交易完成
    w3Provider.eth.wait_for_transaction_receipt(tx_hash)
    
    return True, '交易成功'




class ETHSwap( QMainWindow, Ui_ETHSwapForm): 

    def __init__(self,parent =None):
        super( ETHSwap,self).__init__(parent)
        self.setupUi(self)

        # 打开配置文件，初始化界面数据
        # 左侧
        if os.path.exists( "./ETHSwap.ini"):
            try:
                iniFileDir = os.getcwd() + "\\"+ "ETHSwap.ini"
                with open( iniFileDir, 'r', encoding="utf-8") as iniFile:
                    iniDict = json.loads( iniFile.read())
                if iniDict:
                    if 'filePath' in iniDict:
                        if iniDict['filePath']:
                            self.labelFilePath.setText(iniDict['filePath'])
                            self.mfRefresh(iniDict['filePath'])
                        

                    if 'folderPath' in iniDict:
                        if iniDict['folderPath']:
                            self.labelFolderPath.setText(iniDict['folderPath'])

            except:
                QMessageBox.about( self, "提示", "打开初始化文件ETHSwap.ini异常, 软件关闭时会自动重新创建ETHSwap.ini文件")
        # 右侧
        if os.path.exists( "./ETHSwap_2.ini"):
            try:
                iniFileDir_2 = os.getcwd() + "\\"+ "ETHSwap_2.ini"
                with open( iniFileDir_2, 'r', encoding="utf-8") as iniFile_2:
                    iniDict_2 = json.loads( iniFile_2.read())
                if iniDict_2:
                    if 'filePath' in iniDict_2:
                        if iniDict_2['filePath']:
                            self.labelFilePath_2.setText(iniDict_2['filePath'])
                            self.mfRefresh_2(iniDict_2['filePath'])
                        

                    if 'folderPath' in iniDict_2:
                        if iniDict_2['folderPath']:
                            self.labelFolderPath_2.setText(iniDict_2['folderPath'])

            except:
                QMessageBox.about( self, "提示", "打开初始化文件ETHSwap_2.ini异常, 软件关闭时会自动重新创建ETHSwap_2.ini文件")

        # 初始化交互网络选择cbNetwork
        self.cbNetwork.addItems(["Sepolia Testnet", "Goerli Testnet", "ETH Mainnet", "BSC Mainnet", "BSC Testnet"])
        # 设置twKey的表头
        self.twKey.setHeaderLabel('项目名称')
        self.twKey_2.setHeaderLabel('项目名称')
        # 初始化分类筛选QComboBox
        self.cbFilter.addItems(["选择筛选条件","是否已启用", "是否已废弃"])
        self.cbFilter_2.addItems(["选择筛选条件","是否已启用", "是否已废弃"])

        # 绑定槽函数
        # 中间交易部分
        self.btnCollectAll.clicked.connect(self.mfCollectAll)
        self.btnCollectRandom.clicked.connect(self.mfCollectRandom)
        self.btnCollectPortion.clicked.connect(self.mfCollectPortion)
        self.btnDistributeAverageAll.clicked.connect(self.mfDistributeAverageAll)
        self.btnDistributeAveragePortion.clicked.connect(self.mfDistributeAveragePortion)
        self.btnDistributeRandomAll.clicked.connect(self.mfDistributeRandomAll)
        self.btnDistributeRandomPortion.clicked.connect(self.mfDistributeRandomPortion)
        self.btnPtoPAll.clicked.connect(self.mfPtoPAll)
        self.btnPtoPRandom.clicked.connect(self.mfPtoPRandom)
        self.btnPtoPPortion.clicked.connect(self.mfPtoPPortion)



        # 左侧
        self.btnHelp.clicked.connect(self.mfHelp)
        self.btnNewFile.clicked.connect(self.mfNewFile)
        self.btnOpenFile.clicked.connect(self.mfOpenFile)
        self.btnOpenFolder.clicked.connect(self.mfOpenFolder)
        self.twKey.itemClicked.connect(self.mfClickedTreeItem)
        self.twKey.itemDoubleClicked.connect(self.mfDoubleClickedTreeItem)
        self.cbkmFile.currentIndexChanged.connect(self.mfcbkmFileChanged)
        self.btnKeyAdd.clicked.connect(self.mfKeyAddWindow)
        self.cbFilter.currentIndexChanged.connect(self.mfcbFilterIndexChanged)
        self.btnSelectAll.clicked.connect(self.mfSelectAll)
        self.btnSelectInvert.clicked.connect(self.mfSelectInvert)
        self.btnGetBalance.clicked.connect(self.mfGetBalance)

        #右侧
        self.btnHelp_2.clicked.connect(self.mfHelp_2)
        self.btnNewFile_2.clicked.connect(self.mfNewFile_2)
        self.btnOpenFile_2.clicked.connect(self.mfOpenFile_2)
        self.btnOpenFolder_2.clicked.connect(self.mfOpenFolder_2)
        self.twKey_2.itemClicked.connect(self.mfClickedTreeItem_2)
        self.twKey_2.itemDoubleClicked.connect(self.mfDoubleClickedTreeItem_2)
        self.cbkmFile_2.currentIndexChanged.connect(self.mfcbkmFileChanged_2)
        self.btnKeyAdd_2.clicked.connect(self.mfKeyAddWindow_2)
        self.cbFilter_2.currentIndexChanged.connect(self.mfcbFilterIndexChanged_2)
        self.btnSelectAll_2.clicked.connect(self.mfSelectAll_2)
        self.btnSelectInvert_2.clicked.connect(self.mfSelectInvert_2)
        self.btnGetBalance_2.clicked.connect(self.mfGetBalance_2)

        # 绑定界面上的文本框和复选框
        # 左侧
        self.cbKeyUsed.stateChanged.connect(self.mfcbKeyUsedStateChanged)
        self.cbKeyDisabled.stateChanged.connect(self.mfcbKeyDisabledStateChanged)
        self.leProjectName.editingFinished.connect(self.mfleProjectNameEditingFinished)
        self.leProjectCreationTime.editingFinished.connect(self.mfleProjectCreationTimeEditingFinished)
        self.pteProjectNote.textChanged.connect(self.mfpteProjectNoteTextChanged)
        self.leKeyName.editingFinished.connect(self.mfleKeyNameEditingFinished)
        self.leKeyNumber.editingFinished.connect(self.mfleKeyNumberEditingFinished)
        self.leKeyCreationTime.editingFinished.connect(self.mfleKeyCreationTimeEditingFinished)
        self.pteKeyNote.textChanged.connect(self.mfpteKeyNoteTextChanged)

        # 右侧
        self.cbKeyUsed_2.stateChanged.connect(self.mfcbKeyUsedStateChanged_2)
        self.cbKeyDisabled_2.stateChanged.connect(self.mfcbKeyDisabledStateChanged_2)
        self.leProjectName_2.editingFinished.connect(self.mfleProjectNameEditingFinished_2)
        self.leProjectCreationTime_2.editingFinished.connect(self.mfleProjectCreationTimeEditingFinished_2)
        self.pteProjectNote_2.textChanged.connect(self.mfpteProjectNoteTextChanged_2)
        self.leKeyName_2.editingFinished.connect(self.mfleKeyNameEditingFinished_2)
        self.leKeyNumber_2.editingFinished.connect(self.mfleKeyNumberEditingFinished_2)
        self.leKeyCreationTime_2.editingFinished.connect(self.mfleKeyCreationTimeEditingFinished_2)
        self.pteKeyNote_2.textChanged.connect(self.mfpteKeyNoteTextChanged_2)

    # 左侧查询余额按钮
    def mfGetBalance(self):
        global gDict
        
        leftList = self.mfGetLeftKeyList()
        if not leftList:
            QMessageBox.about(self, '提示', '请在左侧列表中选择要查询的账户')
            return      
        
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  左侧账户列表余额查询:")
        QApplication.processEvents()

        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        
        for i in leftList:
            keyNum = i.split(":")[0].rstrip()
            keyName = i.split(":")[1].rstrip()
            privateKey = gDict['keys'][keyNum]['privateKey']

            self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 余额 " + str(getBalance(privateKey, w3)) + " ETH")
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')        

    # 右侧查询余额按钮
    def mfGetBalance_2(self):
        global gDict_2
        
        rightList = self.mfGetRightKeyList()
        if not rightList:
            QMessageBox.about(self, '提示', '请在右侧列表中选择要查询的账户')
            return      
        
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  右侧账户列表余额查询:")
        QApplication.processEvents()

        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        
        for i in rightList:
            keyNum = i.split(":")[0].rstrip()
            keyName = i.split(":")[1].rstrip()
            privateKey = gDict_2['keys'][keyNum]['privateKey']

            self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 余额 " + str(getBalance(privateKey, w3)) + " ETH")
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')  


    # 左侧twKey全选按钮
    def mfSelectAll(self):
        iterator = QTreeWidgetItemIterator(self.twKey)
        while iterator.value():
            item = iterator.value()
            item.setCheckState(0, Qt.Checked)
            iterator += 1

    # 右侧twKey_2全选按钮
    def mfSelectAll_2(self):
        iterator = QTreeWidgetItemIterator(self.twKey_2)
        while iterator.value():
            item = iterator.value()
            item.setCheckState(0, Qt.Checked)
            iterator += 1

    # 左侧twKey反选按钮
    def mfSelectInvert(self):
        iterator = QTreeWidgetItemIterator(self.twKey)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.Checked:
                item.setCheckState(0, Qt.Unchecked)
            else:
                item.setCheckState(0, Qt.Checked)
            iterator += 1

    # 右侧twKey_2反选按钮
    def mfSelectInvert_2(self):
        iterator = QTreeWidgetItemIterator(self.twKey_2)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.Checked:
                item.setCheckState(0, Qt.Unchecked)
            else:
                item.setCheckState(0, Qt.Checked)
            iterator += 1










    # 已启用复选框cbKeyUsed 状态改变
    # 左侧
    def mfcbKeyUsedStateChanged(self):
        global gDict
        item = self.twKey.selectedItems()
        if item:
            key = item[0].text(0).split(' : ')[0]
            if self.cbKeyUsed.isChecked():
                gDict['keys'][key]['keyUsed'] = True
            else:
                gDict['keys'][key]['keyUsed'] = False
    # 右侧
    def mfcbKeyUsedStateChanged_2(self):
        global gDict_2
        item_2 = self.twKey_2.selectedItems()
        if item_2:
            key_2 = item_2[0].text(0).split(' : ')[0]
            if self.cbKeyUsed_2.isChecked():
                gDict_2['keys'][key_2]['keyUsed'] = True
            else:
                gDict_2['keys'][key_2]['keyUsed'] = False

    # 废弃复选框cbKeyDisabled 状态改变
    # 左侧
    def mfcbKeyDisabledStateChanged(self):
        global gDict
        item = self.twKey.selectedItems()
        if item:
            key = item[0].text(0).split(' : ')[0]
            if self.cbKeyDisabled.isChecked():
                gDict['keys'][key]['keyDisabled'] = True
            else:
                gDict['keys'][key]['keyDisabled'] = False
    # 右侧
    def mfcbKeyDisabledStateChanged_2(self):
        global gDict_2
        item_2 = self.twKey_2.selectedItems()
        if item_2:
            key_2 = item_2[0].text(0).split(' : ')[0]
            if self.cbKeyDisabled_2.isChecked():
                gDict_2['keys'][key_2]['keyDisabled'] = True
            else:
                gDict_2['keys'][key_2]['keyDisabled'] = False

    # 项目名称文本框leProjectName内容改变
    # 左侧
    def mfleProjectNameEditingFinished(self):
        global gDict
        gDict['projectName'] = self.leProjectName.text()
    # 右侧
    def mfleProjectNameEditingFinished_2(self):
        global gDict_2
        gDict_2['projectName'] = self.leProjectName_2.text()


    # 项目创建时间文本框leProjectCreationTime内容改变
    # 左侧
    def mfleProjectCreationTimeEditingFinished(self):
        global gDict
        gDict['projectCreationTime'] = self.leProjectCreationTime.text()
    # 右侧
    def mfleProjectCreationTimeEditingFinished_2(self):
        global gDict_2
        gDict_2['projectCreationTime'] = self.leProjectCreationTime_2.text()

    # 项目备注文本框pteProjectNote内容改变
    # 左侧
    def mfpteProjectNoteTextChanged(self):
        global gDict
        gDict['projectNote'] = self.pteProjectNote.toPlainText()
    # 右侧
    def mfpteProjectNoteTextChanged_2(self):
        global gDict_2
        gDict_2['projectNote'] = self.pteProjectNote_2.toPlainText()

    # 密钥名称文本框leKeyName内容改变
    # 左侧
    def mfleKeyNameEditingFinished(self):
        global gDict
        item = self.twKey.selectedItems()
        if item:
            key = item[0].text(0).split(' : ')[0]
            gDict['keys'][key]['keyName'] = self.leKeyName.text()
            self.mfSaveFile()
            self.mfRefresh(self.labelFilePath.text())     
    # 右侧
    def mfleKeyNameEditingFinished_2(self):
        global gDict_2
        item_2 = self.twKey_2.selectedItems()
        if item_2:
            key_2 = item_2[0].text(0).split(' : ')[0]
            gDict_2['keys'][key_2]['keyName'] = self.leKeyName_2.text()
            self.mfSaveFile_2()
            self.mfRefresh_2(self.labelFilePath_2.text())


    # 密钥序号文本框leKeyNumber内容改变
    # 左侧
    def mfleKeyNumberEditingFinished(self):
        global gDict
        item = self.twKey.selectedItems()
        if item:
            key = item[0].text(0).split(' : ')[0]
            gDict['keys'][key]['keyNumber'] = self.leKeyNumber.text()
    # 右侧
    def mfleKeyNumberEditingFinished_2(self):
        global gDict_2
        item_2 = self.twKey_2.selectedItems()
        if item_2:
            key_2 = item_2[0].text(0).split(' : ')[0]
            gDict_2['keys'][key_2]['keyNumber'] = self.leKeyNumber_2.text()


    # 密钥创建时间文本框leKeyCreationTime内容改变
    # 左侧
    def mfleKeyCreationTimeEditingFinished(self):
        global gDict
        item = self.twKey.selectedItems()
        if item:
            key = item[0].text(0).split(' : ')[0]
            gDict['keys'][key]['keyCreationTime'] = self.leKeyCreationTime.text()
    # 右侧
    def mfleKeyCreationTimeEditingFinished_2(self):
        global gDict_2
        item_2 = self.twKey_2.selectedItems()
        if item_2:
            key_2 = item_2[0].text(0).split(' : ')[0]
            gDict_2['keys'][key_2]['keyCreationTime'] = self.leKeyCreationTime_2.text()

    # 密钥备注文本框pteKeyNote内容改变
    # 左侧
    def mfpteKeyNoteTextChanged(self):
        global gDict
        item = self.twKey.selectedItems()
        if item:
            key = item[0].text(0).split(' : ')[0]
            gDict['keys'][key]['keyNote'] = self.pteKeyNote.toPlainText()
    # 右侧
    def mfpteKeyNoteTextChanged_2(self):
        global gDict_2
        item_2 = self.twKey_2.selectedItems()
        if item_2:
            key_2 = item_2[0].text(0).split(' : ')[0]
            gDict_2['keys'][key_2]['keyNote'] = self.pteKeyNote_2.toPlainText()

    # 按cbFilter的条件分类,刷新twKey
    # 左侧
    def mfcbFilterIndexChanged(self):
        if self.cbFilter.currentIndex() != 0:
            if self.cbFilter.currentText() == "是否已启用":
                # print('是否已启用')
                self.mftwKeySort("是否已启用")
            elif self.cbFilter.currentText() == "是否已废弃":
                # print('是否已废弃')
                self.mftwKeySort("是否已废弃")
    # 右侧
    def mfcbFilterIndexChanged_2(self):
        if self.cbFilter_2.currentIndex() != 0:
            if self.cbFilter_2.currentText() == "是否已启用":
                # print('是否已启用')
                self.mftwKeySort_2("是否已启用")
            elif self.cbFilter_2.currentText() == "是否已废弃":
                # print('是否已废弃')
                self.mftwKeySort_2("是否已废弃")


    # 按照参数分类密钥,刷新twKey
    # 左侧
    def mftwKeySort(self, sortType):
        global gDict
        self.twKey.clear()
        topItemTrue = QTreeWidgetItem(self.twKey)       # 表示筛选条件为真
        topItemFalse = QTreeWidgetItem(self.twKey)
        if sortType == "是否已启用":
            topItemTrue.setText(0, "已启用")
            topItemFalse.setText(0, "未启用")
            self.twKey.addTopLevelItem(topItemTrue)
            self.twKey.addTopLevelItem(topItemFalse)
        elif sortType == "是否已废弃":
            topItemFalse.setText(0, "可使用")
            self.twKey.addTopLevelItem(topItemFalse)
            topItemTrue.setText(0, "已废弃")
            self.twKey.addTopLevelItem(topItemTrue)
            self.twKey.sortItems(0, 0)      # 对顶节点进行排序(column: int, order: SortOrder) 升序对应数值为0，降序对应数值为1。
            
        if gDict:
            for key in gDict['keys']:
                maskedPrivateKey = gDict['keys'][key]['privateKey'][:6] + '****' + gDict['keys'][key]['privateKey'][-6:]
                tempStr = key + ' : ' + gDict['keys'][key]['keyName'] + ' : ' + maskedPrivateKey
                tempItem = QTreeWidgetItem()
                tempItem.setText(0, tempStr)

                if sortType == "是否已启用":
                    if gDict['keys'][key]['keyUsed']:
                        topItemTrue.addChild(tempItem)
                    else:
                        topItemFalse.addChild(tempItem)

                elif sortType == "是否已废弃":
                    if gDict['keys'][key]['keyDisabled']:
                        topItemTrue.addChild(tempItem)
                    else:
                        topItemFalse.addChild(tempItem)

        self.twKey.expandAll()      # 展开所有节点

    # 右侧
    def mftwKeySort_2(self, sortType_2):
        global gDict_2
        self.twKey_2.clear()
        topItemTrue_2 = QTreeWidgetItem(self.twKey_2)       # 表示筛选条件为真
        topItemFalse_2 = QTreeWidgetItem(self.twKey_2)
        if sortType_2 == "是否已启用":
            topItemTrue_2.setText(0, "已启用")
            topItemFalse_2.setText(0, "未启用")
            self.twKey_2.addTopLevelItem(topItemTrue_2)
            self.twKey_2.addTopLevelItem(topItemFalse_2)
        elif sortType_2 == "是否已废弃":
            topItemFalse_2.setText(0, "可使用")
            self.twKey_2.addTopLevelItem(topItemFalse_2)
            topItemTrue_2.setText(0, "已废弃")
            self.twKey_2.addTopLevelItem(topItemTrue_2)
            self.twKey_2.sortItems(0, 0)      # 对顶节点进行排序(column: int, order: SortOrder) 升序对应数值为0，降序对应数值为1。
            
        if gDict_2:
            for key_2 in gDict_2['keys']:
                maskedPrivateKey_2 = gDict_2['keys'][key_2]['privateKey'][:6] + '****' + gDict_2['keys'][key_2]['privateKey'][-6:]
                tempStr_2 = key_2 + ' : ' + gDict_2['keys'][key_2]['keyName'] + ' : ' + maskedPrivateKey_2
                tempItem_2 = QTreeWidgetItem()
                tempItem_2.setText(0, tempStr_2)

                if sortType_2 == "是否已启用":
                    if gDict_2['keys'][key_2]['keyUsed']:
                        topItemTrue_2.addChild(tempItem_2)
                    else:
                        topItemFalse_2.addChild(tempItem_2)

                elif sortType_2 == "是否已废弃":
                    if gDict_2['keys'][key_2]['keyDisabled']:
                        topItemTrue_2.addChild(tempItem_2)
                    else:
                        topItemFalse_2.addChild(tempItem_2)

        self.twKey_2.expandAll()      # 展开所有节点    


    # 使用帮助按钮  注意事项和免责声明
    # 左侧
    def mfHelp(self):
        QMessageBox.about(self, '使用帮助', '1. 点击打开文件夹按钮会在下拉列表框里列出此文件夹下所有的 .km 后缀名文件')
    # 右侧
    def mfHelp_2(self):
        QMessageBox.about(self, '使用帮助', '1. 点击打开文件夹按钮会在下拉列表框里列出此文件夹下所有的 .km 后缀名文件')

    # 新建文件按钮
    # 左侧
    def mfNewFile(self):
        global gDict
        gDict.clear()
        self.twKey.clear()

        try:
            desktopPath = os.path.join(os.path.expanduser("~"), "Desktop")
            tempFolderPath = QFileDialog.getExistingDirectory( self, '选择保存目录', desktopPath, QFileDialog.ShowDirsOnly)
            tempFileName, ok = QInputDialog.getText(self, '新建文件', '请输入新建文件名称:') 
            if ok and tempFolderPath and tempFileName and tempFolderPath != None:
                filePath = tempFolderPath + '/' + tempFileName + '.km'
                if os.path.exists(filePath):
                    QMessageBox.about( self, '提示', '文件名称重复,为了保证数据安全,本软件禁止保存重名文件')
                    return
                f = open( filePath, 'x')
                # 初始化文件中的内容
                gDict = {'projectName':tempFileName, 'projectCreationTime':datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'keyCount': 0,  'projectNote':'新创建的项目,尚未开始操作', 'keys':{}}
                tempJson = json.dumps(gDict, indent=4)
                f.write(tempJson)
                f.close()
            else:
                QMessageBox.about( self, '提示', '文件名或路径错误')
                return

            self.labelFilePath.setText(filePath)
            self.mfRefresh( filePath)
            self.mfKeyAddWindow()

        except:
            QMessageBox.about( self, '提示', '文件创建失败')
            return
    # 右侧
    def mfNewFile_2(self):
        global gDict_2
        gDict_2.clear()
        self.twKey_2.clear()

        try:
            desktopPath_2 = os.path.join(os.path.expanduser("~"), "Desktop")
            tempFolderPath_2 = QFileDialog.getExistingDirectory( self, '选择保存目录', desktopPath_2, QFileDialog.ShowDirsOnly)
            tempFileName_2, ok_2 = QInputDialog.getText(self, '新建文件', '请输入新建文件名称:') 
            if ok_2 and tempFolderPath_2 and tempFileName_2 and tempFolderPath_2 != None:
                filePath_2 = tempFolderPath_2 + '/' + tempFileName_2 + '.km'
                if os.path.exists(filePath_2):
                    QMessageBox.about( self, '提示', '文件名称重复,为了保证数据安全,本软件禁止保存重名文件')
                    return
                f_2 = open( filePath_2, 'x')
                # 初始化文件中的内容
                gDict_2 = {'projectName':tempFileName_2, 'projectCreationTime':datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'keyCount': 0,  'projectNote':'新创建的项目,尚未开始操作', 'keys':{}}
                tempJson_2 = json.dumps(gDict_2, indent=4)
                f_2.write(tempJson_2)
                f_2.close()
            else:
                QMessageBox.about( self, '提示', '文件名或路径错误')
                return

            self.labelFilePath_2.setText(filePath_2)
            self.mfRefresh_2( filePath_2)
            self.mfKeyAddWindow_2()

        except:
            QMessageBox.about( self, '提示', '文件创建失败')
            return

    # 打开文件按钮, 点击按钮打开文件对话框,获得文件路径,传递给mfRefresh()刷新界面
    # 左侧
    def mfOpenFile(self):
        desktopPath = os.path.join(os.path.expanduser("~"), "Desktop")
        # try:
        tempFilePath, uselessFilt = QFileDialog.getOpenFileName( self, '打开KeyManager文件', desktopPath, 'KeyManager(*.km)', 'KeyManager(*.km)')
        if tempFilePath != '':
            self.labelFilePath.setText(tempFilePath)
            # print( '1',tempFilePath)
            self.mfRefresh(tempFilePath)
            # print( '2',tempFilePath)
        else:
            QMessageBox.about( self, "提示", "请选择后缀名为 .km 的文件。")
        # except:
        #     QMessageBox.about( self, "提示", "选择KeyManager文件失败,请重新选择。")
    # 右侧
    def mfOpenFile_2(self):
        desktopPath_2 = os.path.join(os.path.expanduser("~"), "Desktop")
        # try:
        tempFilePath_2, uselessFilt_2 = QFileDialog.getOpenFileName( self, '打开KeyManager文件', desktopPath_2, 'KeyManager(*.km)', 'KeyManager(*.km)')
        if tempFilePath_2 != '':
            self.labelFilePath_2.setText(tempFilePath_2)
            # print( '1',tempFilePath)
            self.mfRefresh_2(tempFilePath_2)
            # print( '2',tempFilePath)
        else:
            QMessageBox.about( self, "提示", "请选择后缀名为 .km 的文件。")
        # except:
        #     QMessageBox.about( self, "提示", "选择KeyManager文件失败,请重新选择。")

    # 打开文件夹按钮,点击打开文件夹按钮,弹出打开文件夹对话框,获得文件夹路径后,搜索所有.km后缀名的文件,并把文件名添加到cbFolderPathList中
    # 左侧
    def mfOpenFolder(self):
        self.cbkmFile.clear()
        try:
            desktopPath = os.path.join(os.path.expanduser("~"), "Desktop")
            tempFolderPath = QFileDialog.getExistingDirectory( self, '选择目录', desktopPath, QFileDialog.ShowDirsOnly)

            kmFiles = []

            for root, dirs, files in os.walk(tempFolderPath):
                for file in files:
                    if file.endswith(".km"):
                        full_path = os.path.join(root, file)
                        relative_path = os.path.relpath(full_path, tempFolderPath)
                        kmFiles.append(relative_path)
            
            # print(kmFiles)
            tempItem = "搜索到 " + str(len(kmFiles)) + " 个文件"
            self.cbkmFile.addItem( tempItem)
            self.cbkmFile.addItems(kmFiles)
            self.labelFolderPath.setText(tempFolderPath)
        except:
            QMessageBox.about( self, '提示', '搜索.km文件失败')
            return
    # 右侧
    def mfOpenFolder_2(self):
        self.cbkmFile_2.clear()
        try:
            desktopPath_2 = os.path.join(os.path.expanduser("~"), "Desktop")
            tempFolderPath_2 = QFileDialog.getExistingDirectory( self, '选择目录', desktopPath_2, QFileDialog.ShowDirsOnly)

            kmFiles_2 = []

            for root_2, dirs_2, files_2 in os.walk(tempFolderPath_2):
                for file_2 in files_2:
                    if file_2.endswith(".km"):
                        full_path_2 = os.path.join(root_2, file_2)
                        relative_path_2 = os.path.relpath(full_path_2, tempFolderPath_2)
                        kmFiles_2.append(relative_path_2)
            
            # print(kmFiles_2)
            tempItem_2 = "搜索到 " + str(len(kmFiles_2)) + " 个文件"
            self.cbkmFile_2.addItem( tempItem_2)
            self.cbkmFile_2.addItems(kmFiles_2)
            self.labelFolderPath_2.setText(tempFolderPath_2)
        except:
            QMessageBox.about( self, '提示', '搜索.km文件失败')
            return

    # 下拉列表框self.cbkmFile选择的项改变
    # 左侧
    def mfcbkmFileChanged(self):
        rootPath = self.labelFolderPath.text()
        relativePath = self.cbkmFile.currentText()
        # print(rootPath, relativePath)
        filePath = os.path.join(rootPath, relativePath)
        # print(filePath)

        if filePath[-3:] != '.km':
            return
        
        if os.path.exists(filePath):
            self.labelFilePath.setText(filePath)
            self.mfRefresh(filePath)
        else:
            QMessageBox.information(self, "提示", filePath + " 文件不存在")
    # 右侧
    def mfcbkmFileChanged_2(self):
        rootPath_2 = self.labelFolderPath_2.text()
        relativePath_2 = self.cbkmFile_2.currentText()
        # print(rootPath_2, relativePath_2)
        filePath_2 = os.path.join(rootPath_2, relativePath_2)
        # print(filePath_2)

        if filePath_2[-3:] != '.km':
            return
        
        if os.path.exists(filePath_2):
            self.labelFilePath_2.setText(filePath_2)
            self.mfRefresh_2(filePath_2)
        else:
            QMessageBox.information(self, "提示", filePath_2 + " 文件不存在")


    # 保存按钮,点击保存,把全局字典gDict转换为json格式,保存在当前打开的文件self.labelFilePath.text()中
    # 左侧
    def mfSaveFile(self):
        global gDict
        saveFilePath = self.labelFilePath.text()
        saveJson = json.dumps( gDict, indent=4)
        try:
            saveFile = open( saveFilePath, "w",  encoding="utf-8")
            saveFile.write( saveJson)
            saveFile.close()
        except:
            QMessageBox.about( self, "提示", "保存KeyManager数据文件.km失败")
    # 右侧
    def mfSaveFile_2(self):
        global gDict_2
        saveFilePath_2 = self.labelFilePath_2.text()
        saveJson_2 = json.dumps( gDict_2, indent=4)
        try:
            saveFile_2 = open( saveFilePath_2, "w",  encoding="utf-8")
            saveFile_2.write( saveJson_2)
            saveFile_2.close()
        except:
            QMessageBox.about( self, "提示", "保存KeyManager数据文件.km失败")

    # 单击twKey中的项   把地址复制到剪贴板,并在界面右边显示被点击项的信息
    # 左侧
    def mfClickedTreeItem(self, item, column):
        global gDict
        key = item.text(0).split(' : ')[0]
        if key[0] == 'k':       # 'k'是指'key'的第一个字符. item可能是"已启用" "未启用" "已废弃"这些顶层分类的名字,所以要判断key的值
            pyperclip.copy(gDict['keys'][key]['keyAddress'])
            self.mfDisplayItemInfo(item)
    # 右侧
    def mfClickedTreeItem_2(self, item_2, column_2):
        global gDict_2
        key_2 = item_2.text(0).split(' : ')[0]
        if key_2[0] == 'k':       # 'k'是指'key'的第一个字符. item可能是"已启用" "未启用" "已废弃"这些顶层分类的名字,所以要判断key的值
            pyperclip.copy(gDict_2['keys'][key_2]['keyAddress'])
            self.mfDisplayItemInfo_2(item_2)

    # 双击twKey中的项   把私钥复制到剪贴板,并在界面右边显示被点击项的信息
    # 左侧
    def mfDoubleClickedTreeItem(self, item, column):
        global gDict
        key = item.text(0).split(' : ')[0]
        pyperclip.copy(gDict['keys'][key]['privateKey'])
        self.mfDisplayItemInfo(item)
    # 右侧
    def mfDoubleClickedTreeItem_2(self, item_2, column_2):
        global gDict_2
        key_2 = item_2.text(0).split(' : ')[0]
        pyperclip.copy(gDict_2['keys'][key_2]['privateKey'])
        self.mfDisplayItemInfo_2(item_2)

    # 传递一个twKey中的项,在界面右边显示被点击项的信息
    # 左侧
    def mfDisplayItemInfo(self, item):
        global gDict
        key = item.text(0).split(' : ')[0]
        # 更新界面右侧的文本框
        self.leProjectName.setText(gDict['projectName'])
        self.leProjectCreationTime.setText(gDict['projectCreationTime'])
        self.leKeyCount.setText(str(len(gDict['keys'])))
        self.pteProjectNote.setPlainText( gDict['projectNote'])
        self.leKeyName.setText(gDict['keys'][key]['keyName'])
        self.leKeyNumber.setText(str(gDict['keys'][key]['keyNumber']))
        self.leKeyCreationTime.setText(gDict['keys'][key]['keyCreationTime'])
        self.pteKeyNote.setPlainText(gDict['keys'][key]['keyNote'])
        self.ptePrivateKey.setPlainText(gDict['keys'][key]['privateKey'])
        self.ptePublicKey.setPlainText(gDict['keys'][key]['publicKey'])
        self.pteKeyAddress.setPlainText(gDict['keys'][key]['keyAddress'])
        self.pteKeyMnemonic.setPlainText(gDict['keys'][key]['keyMnemonic'])

        if gDict['keys'][key]['keyUsed'] == True:
            self.cbKeyUsed.setChecked(True)
        else:
            self.cbKeyUsed.setChecked(False)
        
        if gDict['keys'][key]['keyDisabled'] == True:
            self.cbKeyDisabled.setChecked(True)
        else:
            self.cbKeyDisabled.setChecked(False)
    # 右侧
    def mfDisplayItemInfo_2(self, item_2):
        global gDict_2
        key_2 = item_2.text(0).split(' : ')[0]
        # 更新界面右侧的文本框
        self.leProjectName_2.setText(gDict_2['projectName'])
        self.leProjectCreationTime_2.setText(gDict_2['projectCreationTime'])
        self.leKeyCount_2.setText(str(len(gDict_2['keys'])))
        self.pteProjectNote_2.setPlainText( gDict_2['projectNote'])
        self.leKeyName_2.setText(gDict_2['keys'][key_2]['keyName'])
        self.leKeyNumber_2.setText(str(gDict_2['keys'][key_2]['keyNumber']))
        self.leKeyCreationTime_2.setText(gDict_2['keys'][key_2]['keyCreationTime'])
        self.pteKeyNote_2.setPlainText(gDict_2['keys'][key_2]['keyNote'])
        self.ptePrivateKey_2.setPlainText(gDict_2['keys'][key_2]['privateKey'])
        self.ptePublicKey_2.setPlainText(gDict_2['keys'][key_2]['publicKey'])
        self.pteKeyAddress_2.setPlainText(gDict_2['keys'][key_2]['keyAddress'])
        self.pteKeyMnemonic_2.setPlainText(gDict_2['keys'][key_2]['keyMnemonic'])

        if gDict_2['keys'][key_2]['keyUsed'] == True:
            self.cbKeyUsed_2.setChecked(True)
        else:
            self.cbKeyUsed_2.setChecked(False)
        
        if gDict_2['keys'][key_2]['keyDisabled'] == True:
            self.cbKeyDisabled_2.setChecked(True)
        else:
            self.cbKeyDisabled_2.setChecked(False)

    # 新增密钥,更新全局字典gDict和刷新twKey
    # 左侧
    def mfKeyAddWindow(self):
        self.windowKeyAdd = keyAdd()
        self.windowKeyAdd.show()

        self.windowKeyAdd.signalToETHSwap.connect(self.mfKeyAdd)
    # 右侧
    def mfKeyAddWindow_2(self):
        self.windowKeyAdd_2 = keyAdd()
        self.windowKeyAdd_2.show()

        self.windowKeyAdd_2.signalToETHSwap.connect(self.mfKeyAdd_2)

    # 根据windowKeyAdd发送过来的参数,创建密钥,并调用mfRefresh刷新界面
    # 左侧
    def mfKeyAdd(self, keyType, keyCount):
        # print(keyType, keyCount)
        global gDict
        
        walletsList = generate_wallets(keyType, keyCount)
        for i in walletsList:
            keyNumber = gDict['keyCount'] + 1
            gDict['keyCount'] += 1
            gDict['keys'][f"key{keyNumber}"] = {"keyName": f"key{keyNumber}", 
                                                "keyCreationTime": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                                                "keyNote": "There are no key note",
                                                "keyNumber": keyNumber, 
                                                "keyUsed": False,
                                                "keyDisabled": False,
                                                "privateKey": i["private_key"], 
                                                "publicKey": i["public_key"], 
                                                "keyAddress": i["address"], 
                                                "keyMnemonic": i["mnemonic"]
                                                }
            
        # 先保存到文件中,再调用mfRefresh()更新界面
        self.mfSaveFile()
        self.mfRefresh(self.labelFilePath.text())
    # 右侧
    def mfKeyAdd_2(self, keyType_2, keyCount_2):
        # print(keyType, keyCount)
        global gDict_2
        
        walletsList_2 = generate_wallets(keyType_2, keyCount_2)
        for i_2 in walletsList_2:
            keyNumber_2 = gDict_2['keyCount'] + 1
            gDict_2['keyCount'] += 1
            gDict_2['keys'][f"key{keyNumber_2}"] = {"keyName": f"key{keyNumber_2}", 
                                                "keyCreationTime": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                                                "keyNote": "There are no key note",
                                                "keyNumber": keyNumber_2, 
                                                "keyUsed": False,
                                                "keyDisabled": False,
                                                "privateKey": i_2["private_key"], 
                                                "publicKey": i_2["public_key"], 
                                                "keyAddress": i_2["address"], 
                                                "keyMnemonic": i_2["mnemonic"]
                                                }
            
        # 先保存到文件中,再调用mfRefresh_2()更新界面
        self.mfSaveFile_2()
        self.mfRefresh_2(self.labelFilePath_2.text())


    # 根据传递的文件路径,刷新lwKey和界面   
    # 左侧
    def mfRefresh(self, kmPath):
        global gDict
        self.twKey.clear()
        if not os.path.exists( kmPath):
            QMessageBox.about( self, '提示', '文件名或路径错误,可能是保存的密钥文件.km已被移除')
            self.labelFilePath.setText("选择文件")
            self.labelFolderPath.setText("选择文件夹")
            return
        
        # try:
        with open( kmPath, 'r', encoding="utf-8") as kmFile:
            gDict = json.loads( kmFile.read())
        if gDict:
            # root = QTreeWidgetItem(self.twKey)
            # root.setText(0, gDict['project_name'])
            self.twKey.setHeaderLabel(gDict['projectName'])

            for key in gDict['keys']:
                maskedPrivateKey = gDict['keys'][key]['privateKey'][:6] + '****' + gDict['keys'][key]['privateKey'][-6:]
                tempStr = key + ' : ' + gDict['keys'][key]['keyName'] + ' : ' + maskedPrivateKey
                tempItem = QTreeWidgetItem()
                tempItem.setText(0, tempStr)
                tempItem.setCheckState(0, Qt.Unchecked)
                self.twKey.addTopLevelItem( tempItem)

                # print( tempStr)




            # print(gDict['project_name'])

        # except:
        #     QMessageBox.about( self, "提示", "打开.km文件异常, 请检查文件是否正确并重新打开")
    # 右侧
    def mfRefresh_2(self, kmPath_2):
        global gDict_2
        self.twKey_2.clear()
        if not os.path.exists( kmPath_2):
            QMessageBox.about( self, '提示', '文件名或路径错误,可能是保存的密钥文件.km已被移除')
            self.labelFilePath_2.setText("选择文件")
            self.labelFolderPath_2.setText("选择文件夹")
            return
        
        # try:
        with open( kmPath_2, 'r', encoding="utf-8") as kmFile_2:
            gDict_2 = json.loads( kmFile_2.read())
        if gDict_2:
            # root = QTreeWidgetItem(self.twKey)
            # root.setText(0, gDict['project_name'])
            self.twKey_2.setHeaderLabel(gDict_2['projectName'])

            for key_2 in gDict_2['keys']:
                maskedPrivateKey_2 = gDict_2['keys'][key_2]['privateKey'][:6] + '****' + gDict_2['keys'][key_2]['privateKey'][-6:]
                tempStr_2 = key_2 + ' : ' + gDict_2['keys'][key_2]['keyName'] + ' : ' + maskedPrivateKey_2
                tempItem_2 = QTreeWidgetItem()
                tempItem_2.setText(0, tempStr_2)
                tempItem_2.setCheckState(0, Qt.Unchecked)
                self.twKey_2.addTopLevelItem( tempItem_2)

                # print( tempStr_2)




            # print(gDict_2['project_name'])

        # except:
        #     QMessageBox.about( self, "提示", "打开.km文件异常, 请检查文件是否正确并重新打开")


    # 交易部分
    # 获得左侧列表中被选中的私钥的列表
    def mfGetLeftKeyList(self):
        global gDict
        # print(gDict)
        leftList = []
        iterator = QTreeWidgetItemIterator(self.twKey)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.Checked:
                # 下面是只向列表中添加私钥
                # key = item.text(0).split(':')[0].rstrip()
                # leftList.append(gDict['keys'][key]['privateKey'])
                # 下面是向列表中添加item整个字符串
                itemStr = item.text(0).rstrip()
                leftList.append(itemStr)
            iterator += 1
        # print(leftList)
        return leftList

    # 获得右侧列表中被选中的私钥的列表
    def mfGetRightKeyList(self):
        rightList = []
        iterator_2 = QTreeWidgetItemIterator(self.twKey_2)
        while iterator_2.value():
            item_2 = iterator_2.value()
            if item_2.checkState(0) == Qt.Checked:
                # 下面是只向列表中添加私钥
                # key_2 = item_2.text(0).split(':')[0].rstrip()
                # rightList.append(gDict_2['keys'][key_2]['privateKey'])
                # 下面是向列表中添加item整个字符串
                itemStr_2 = item_2.text(0).rstrip()
                rightList.append(itemStr_2)
            iterator_2 += 1

        return rightList

# 交易-------------------------------------------------------------------------------------------------------------------
    # 归集账户上的所有资金
    def mfCollectAll(self):
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  把左侧选中账户的所有资金转移到右侧单一账户")
        QApplication.processEvents()

        global gDict, gDict_2
        
        leftList = self.mfGetLeftKeyList()
        if not leftList:
            QMessageBox.about(self, '提示', '请在左侧列表中选择需要交互的账户')
            return

        rightList = self.mfGetRightKeyList()
        if len(rightList) != 1:
            QMessageBox.about(self, '提示', '请在右侧列表中选择接收资金的账户,有且只能有一个')
            return

        receiverKeyNum = rightList[0].split(':')[0].rstrip()
        receiverPrivateKey = gDict_2['keys'][receiverKeyNum]['privateKey']
        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        chainID = getChainID(networkName)
        for i in leftList:
            keyNum = i.split(":")[0].rstrip()
            keyName = i.split(":")[1].rstrip()
            privateKey = gDict['keys'][keyNum]['privateKey']
            value = getBalance(privateKey, w3)
            value = w3.to_wei(value, 'ether')
            gas_limit = 21000       # 发送以太币所需的标准gas数量
            amount = value - w3.eth.gas_price * gas_limit
            # 判断转账金额在
            if not 1 < amount < 2**256 - 1:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 账户金额不足")
                QApplication.processEvents()
                continue
            amount = w3.from_wei(amount, 'ether')
            # print( value, gas_limit, w3.eth.gas_price, amount)
            # gas_price gas_limit 参数可以是0, 在函数中 gas_price会自动获取, gas_limit 默认21000
            # transfer_eth返回值是一个元组, 第一个值是bool,表示是否成功.  第二个值是字符串,表示成功或错误的信息
            result = transfer_eth(w3, privateKey, receiverPrivateKey, chainID, amount, 0, 0)   
            if result[0]:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 转账 " + str(amount) + "ETH  成功")
            else:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 转账 " + str(amount) + "ETH  失败****  " + result[1])
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')


    # 归集账户上的部分资金
    def mfCollectPortion(self):
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  把左侧选中账户的部分资金转移到右侧单一账户")
        QApplication.processEvents()
        
        global gDict, gDict_2
        
        leftList = self.mfGetLeftKeyList()
        if not leftList:
            QMessageBox.about(self, '提示', '请在左侧列表中选择需要交互的账户')
            return

        rightList = self.mfGetRightKeyList()
        if len(rightList) != 1:
            QMessageBox.about(self, '提示', '请在右侧列表中选择接收资金的账户,有且只能有一个')
            return

        receiverKeyNum = rightList[0].split(':')[0].rstrip()
        receiverPrivateKey = gDict_2['keys'][receiverKeyNum]['privateKey']
        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        chainID = getChainID(networkName)
        for i in leftList:
            keyNum = i.split(":")[0].rstrip()
            keyName = i.split(":")[1].rstrip()
            privateKey = gDict['keys'][keyNum]['privateKey']
            value = self.dsbValuePortion.value()
            value = w3.to_wei(value, 'ether')
            gas_limit = 21000       # 发送以太币所需的标准gas数量
            amount = value - w3.eth.gas_price * gas_limit
            # 判断转账金额在
            if not 1 < amount < 2**256 - 1:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 账户金额不足")
                QApplication.processEvents()
                continue
            amount = w3.from_wei(amount, 'ether')
            # print( value, gas_limit, w3.eth.gas_price, amount)
            # gas_price gas_limit 参数可以是0, 在函数中 gas_price会自动获取, gas_limit 默认21000
            # transfer_eth返回值是一个元组, 第一个值是bool,表示是否成功.  第二个值是字符串,表示成功或错误的信息
            result = transfer_eth(w3, privateKey, receiverPrivateKey, chainID, amount, 0, 0)   
            if result[0]:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 转账 " + str(amount) + "ETH  成功")
            else:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 转账 " + str(amount) + "ETH  失败****  " + result[1])
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')


    # 归集随机金额的资金
    def mfCollectRandom(self):
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  把左侧选中账户的随机金额转移到右侧单一账户")
        QApplication.processEvents()
        
        global gDict, gDict_2
        
        leftList = self.mfGetLeftKeyList()
        if not leftList:
            QMessageBox.about(self, '提示', '请在左侧列表中选择需要交互的账户')
            return

        rightList = self.mfGetRightKeyList()
        if len(rightList) != 1:
            QMessageBox.about(self, '提示', '请在右侧列表中选择接收资金的账户,有且只能有一个')
            return

        receiverKeyNum = rightList[0].split(':')[0].rstrip()
        receiverPrivateKey = gDict_2['keys'][receiverKeyNum]['privateKey']
        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        chainID = getChainID(networkName)
        for i in leftList:
            keyNum = i.split(":")[0].rstrip()
            keyName = i.split(":")[1].rstrip()
            privateKey = gDict['keys'][keyNum]['privateKey']

            valueMax = getBalance(privateKey, w3)
            value = random.uniform(0.0001, float(valueMax))
            value = w3.to_wei(value, 'ether')
            gas_limit = 21000       # 发送以太币所需的标准gas数量
            amount = value - w3.eth.gas_price * gas_limit
            # 判断转账金额在
            if not 1 < amount < 2**256 - 1:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 账户金额不足")
                QApplication.processEvents()
                continue
            amount = w3.from_wei(amount, 'ether')
            # print( value, gas_limit, w3.eth.gas_price, amount)
            # gas_price gas_limit 参数可以是0, 在函数中 gas_price会自动获取, gas_limit 默认21000
            # transfer_eth返回值是一个元组, 第一个值是bool,表示是否成功.  第二个值是字符串,表示成功或错误的信息
            result = transfer_eth(w3, privateKey, receiverPrivateKey, chainID, amount, 0, 0)   
            if result[0]:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 转账 " + str(amount) + "ETH  成功")
            else:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 转账 " + str(amount) + "ETH  失败****  " + result[1])
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')


    # 所有资金平均分发
    def mfDistributeAverageAll(self):
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  把左侧单一账户所有资金平均分发到右侧选中账户")
        QApplication.processEvents()
        
        global gDict, gDict_2
        
        leftList = self.mfGetLeftKeyList()
        if len(leftList) != 1:
            QMessageBox.about(self, '提示', '请在左侧列表中选择分发资金的账户,有且只能有一个')
            return

        rightList = self.mfGetRightKeyList()
        if not rightList:
            QMessageBox.about(self, '提示', '请在右侧列表中选择需要交互的账户')
            return        

        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        chainID = getChainID(networkName)

        senderKeyNum = leftList[0].split(':')[0].rstrip()
        senderKeyName = leftList[0].split(':')[1].rstrip()
        senderPrivateKey = gDict['keys'][senderKeyNum]['privateKey']
        count = len(rightList)
        gas_limit = 21000       # 发送以太币所需的标准gas数量
        totalETH = getBalance(senderPrivateKey, w3)
        totalWei = w3.to_wei(totalETH, 'ether') - w3.eth.gas_price * gas_limit * (count + 1)  # *(count + 1) 多减去一个gas,以免gas不足
        averageWei = totalWei // count
        print("每一份的金额", averageWei)

        if averageWei <= 0:
            self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + senderKeyNum + " " + senderKeyName + " 账户金额不足")
            QApplication.processEvents()
            return
        
        for i in rightList:
            keyNum = i.split(":")[0].rstrip()
            keyName = i.split(":")[1].rstrip()
            privateKey = gDict_2['keys'][keyNum]['privateKey']

            amount = w3.from_wei(averageWei, 'ether')
            # print( value, gas_limit, w3.eth.gas_price, amount)
            # gas_price gas_limit 参数可以是0, 在函数中 gas_price会自动获取, gas_limit 默认21000
            # transfer_eth返回值是一个元组, 第一个值是bool,表示是否成功.  第二个值是字符串,表示成功或错误的信息
            result = transfer_eth(w3, senderPrivateKey, privateKey, chainID, amount, 0, 0)   
            if result[0]:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 接收转账 " + str(amount) + "ETH  成功")
            else:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 接收转账 " + str(amount) + "ETH  失败****  " + result[1])
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')



    # 部分资金平均分发
    def mfDistributeAveragePortion(self):
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  把左侧单一账户部分资金平均分发到右侧选中账户")
        QApplication.processEvents()
        
        global gDict, gDict_2
        
        leftList = self.mfGetLeftKeyList()
        if len(leftList) != 1:
            QMessageBox.about(self, '提示', '请在左侧列表中选择分发资金的账户,有且只能有一个')
            return

        rightList = self.mfGetRightKeyList()
        if not rightList:
            QMessageBox.about(self, '提示', '请在右侧列表中选择需要交互的账户')
            return        

        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        chainID = getChainID(networkName)

        senderKeyNum = leftList[0].split(':')[0].rstrip()
        senderKeyName = leftList[0].split(':')[1].rstrip()
        senderPrivateKey = gDict['keys'][senderKeyNum]['privateKey']
        count = len(rightList)
        gas_limit = 21000       # 发送以太币所需的标准gas数量
        totalETH = self.dsbValueDistributeAverage.value()
        totalWei = w3.to_wei(totalETH, 'ether') - w3.eth.gas_price * gas_limit * (count + 1)  # *(count + 1) 多减去一个gas,以免gas不足
        averageWei = totalWei // count
        print("每一份的金额", averageWei)

        if averageWei <= 0:
            self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + senderKeyNum + " " + senderKeyName + " 账户金额不足")
            QApplication.processEvents()
            return
        
        for i in rightList:
            keyNum = i.split(":")[0].rstrip()
            keyName = i.split(":")[1].rstrip()
            privateKey = gDict_2['keys'][keyNum]['privateKey']

            amount = w3.from_wei(averageWei, 'ether')
            # print( value, gas_limit, w3.eth.gas_price, amount)
            # gas_price gas_limit 参数可以是0, 在函数中 gas_price会自动获取, gas_limit 默认21000
            # transfer_eth返回值是一个元组, 第一个值是bool,表示是否成功.  第二个值是字符串,表示成功或错误的信息
            result = transfer_eth(w3, senderPrivateKey, privateKey, chainID, amount, 0, 0)   
            if result[0]:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 接收转账 " + str(amount) + "ETH  成功")
            else:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 接收转账 " + str(amount) + "ETH  失败****  " + result[1])
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')



    # 所有资金随机分发
    def mfDistributeRandomAll(self):
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  把左侧单一账户所有资金随机分发到右侧选中账户")
        QApplication.processEvents()
        
        global gDict, gDict_2
        
        leftList = self.mfGetLeftKeyList()
        if len(leftList) != 1:
            QMessageBox.about(self, '提示', '请在左侧列表中选择分发资金的账户,有且只能有一个')
            return

        rightList = self.mfGetRightKeyList()
        if not rightList:
            QMessageBox.about(self, '提示', '请在右侧列表中选择需要交互的账户')
            return        

        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        chainID = getChainID(networkName)

        senderKeyNum = leftList[0].split(':')[0].rstrip()
        senderKeyName = leftList[0].split(':')[1].rstrip()
        senderPrivateKey = gDict['keys'][senderKeyNum]['privateKey']
        count = len(rightList)
        gas_limit = 21000       # 发送以太币所需的标准gas数量

        totalETH = getBalance(senderPrivateKey, w3)
        totalWei = w3.to_wei(totalETH, 'ether') - w3.eth.gas_price * gas_limit * (count + 2)  # *(count + 2) 多减去两个gas,以免gas不足
        totalETH = w3.from_wei(totalWei, 'ether')
        randomETHList = split_number(round(totalETH, 4), count)
        # print("随机金额的列表", randomWeiList)
        
        for i, amount in zip(rightList, randomETHList):
            keyNum = i.split(":")[0].rstrip()
            keyName = i.split(":")[1].rstrip()
            privateKey = gDict_2['keys'][keyNum]['privateKey']

            if amount <= 0:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + senderKeyNum + " " + senderKeyName + " 转账金额随机数为0,跳过当前账户")
                QApplication.processEvents()
                continue

            # gas_price gas_limit 参数可以是0, 在函数中 gas_price会自动获取, gas_limit 默认21000
            # transfer_eth返回值是一个元组, 第一个值是bool,表示是否成功.  第二个值是字符串,表示成功或错误的信息
            result = transfer_eth(w3, senderPrivateKey, privateKey, chainID, amount, 0, 0)   
            if result[0]:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 接收转账 " + str(amount) + "ETH  成功")
            else:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 接收转账 " + str(amount) + "ETH  失败****  " + result[1])
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')



    # 部分资金随机分发
    def mfDistributeRandomPortion(self):
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  把左侧单一账户指定金额随机分发到右侧选中账户")
        QApplication.processEvents()
        
        global gDict, gDict_2
        
        leftList = self.mfGetLeftKeyList()
        if len(leftList) != 1:
            QMessageBox.about(self, '提示', '请在左侧列表中选择分发资金的账户,有且只能有一个')
            return

        rightList = self.mfGetRightKeyList()
        if not rightList:
            QMessageBox.about(self, '提示', '请在右侧列表中选择需要交互的账户')
            return        

        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        chainID = getChainID(networkName)

        senderKeyNum = leftList[0].split(':')[0].rstrip()
        senderKeyName = leftList[0].split(':')[1].rstrip()
        senderPrivateKey = gDict['keys'][senderKeyNum]['privateKey']
        count = len(rightList)
        gas_limit = 21000       # 发送以太币所需的标准gas数量

        totalETH = self.dsbValueDistributeRandom.value()
        totalWei = w3.to_wei(totalETH, 'ether') - w3.eth.gas_price * gas_limit * (count + 2)  # *(count + 2) 多减去两个gas,以免gas不足
        totalETH = w3.from_wei(totalWei, 'ether')
        randomETHList = split_number(round(totalETH, 4), count)
        # print("随机金额的列表", randomWeiList)
        
        for i, amount in zip(rightList, randomETHList):
            keyNum = i.split(":")[0].rstrip()
            keyName = i.split(":")[1].rstrip()
            privateKey = gDict_2['keys'][keyNum]['privateKey']

            if amount <= 0:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + senderKeyNum + " " + senderKeyName + " 转账金额随机数为0,跳过当前账户")
                QApplication.processEvents()
                continue

            # gas_price gas_limit 参数可以是0, 在函数中 gas_price会自动获取, gas_limit 默认21000
            # transfer_eth返回值是一个元组, 第一个值是bool,表示是否成功.  第二个值是字符串,表示成功或错误的信息
            result = transfer_eth(w3, senderPrivateKey, privateKey, chainID, amount, 0, 0)   
            if result[0]:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 接收转账 " + str(amount) + "ETH  成功")
            else:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + keyNum + " " + keyName + " 接收转账 " + str(amount) + "ETH  失败****  " + result[1])
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')

# 一对一转账所有资金
    def mfPtoPAll(self):
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  把左侧选中账户的所有资金一对一转到右侧选中账户")
        QApplication.processEvents()
        
        global gDict, gDict_2
        
        leftList = self.mfGetLeftKeyList()
        rightList = self.mfGetRightKeyList()
        if len(leftList) != len(rightList):
            QMessageBox.about(self, '提示', '请左右两侧选择相同数量的账户')
            return        

        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        chainID = getChainID(networkName)

        for left, right in zip(leftList, rightList):
            leftKeyNum = left.split(':')[0].rstrip()
            leftKeyName = left.split(':')[1].rstrip()
            leftPrivateKey = gDict['keys'][leftKeyNum]['privateKey']
            rightKeyNum = right.split(':')[0].rstrip()
            rightKeyName = right.split(':')[1].rstrip()
            rightPrivateKey = gDict_2['keys'][rightKeyNum]['privateKey']

            gas_limit = 21000       # 发送以太币所需的标准gas数量
            totalETH = getBalance(leftPrivateKey, w3)
            totalWei = w3.to_wei(totalETH, 'ether')
            amountWei = totalWei - w3.eth.gas_price * gas_limit
            amountETH = w3.from_wei(amountWei, 'ether')

            if amountETH <= 0:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + leftKeyNum + " " + leftKeyName + " 转账金额<=0 跳过此转账")
                QApplication.processEvents()
                continue

            # gas_price gas_limit 参数可以是0, 在函数中 gas_price会自动获取, gas_limit 默认21000
            # transfer_eth返回值是一个元组, 第一个值是bool,表示是否成功.  第二个值是字符串,表示成功或错误的信息
            result = transfer_eth(w3, leftPrivateKey, rightPrivateKey, chainID, amountETH, 0, 0)   
            if result[0]:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + leftKeyNum + " " + leftKeyName + 
                                  " 发送到 " + rightKeyNum + " " + rightKeyName + " " + str(amountETH) + "ETH  成功")
            else:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + leftKeyNum + " " + leftKeyName + 
                                  " 发送到 " + rightKeyNum + " " + rightKeyName + " " + str(amountETH) + "ETH  失败")
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')

# 一对一转账随机资金
    def mfPtoPRandom(self):
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  把左侧选中账户的随机金额一对一转到右侧选中账户")
        QApplication.processEvents()
        
        global gDict, gDict_2
        
        leftList = self.mfGetLeftKeyList()
        rightList = self.mfGetRightKeyList()
        if len(leftList) != len(rightList):
            QMessageBox.about(self, '提示', '请左右两侧选择相同数量的账户')
            return        

        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        chainID = getChainID(networkName)

        for left, right in zip(leftList, rightList):
            leftKeyNum = left.split(':')[0].rstrip()
            leftKeyName = left.split(':')[1].rstrip()
            leftPrivateKey = gDict['keys'][leftKeyNum]['privateKey']
            rightKeyNum = right.split(':')[0].rstrip()
            rightKeyName = right.split(':')[1].rstrip()
            rightPrivateKey = gDict_2['keys'][rightKeyNum]['privateKey']

            gas_limit = 21000       # 发送以太币所需的标准gas数量
            totalETH = random.uniform(0.0001, float(round(getBalance(leftPrivateKey, w3), 4)))
            totalWei = w3.to_wei(totalETH, 'ether')
            amountWei = totalWei - w3.eth.gas_price * gas_limit
            amountETH = w3.from_wei(amountWei, 'ether')

            if amountETH <= 0:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + leftKeyNum + " " + leftKeyName + " 转账金额<=0 跳过此转账")
                QApplication.processEvents()
                continue

            # gas_price gas_limit 参数可以是0, 在函数中 gas_price会自动获取, gas_limit 默认21000
            # transfer_eth返回值是一个元组, 第一个值是bool,表示是否成功.  第二个值是字符串,表示成功或错误的信息
            result = transfer_eth(w3, leftPrivateKey, rightPrivateKey, chainID, amountETH, 0, 0)   
            if result[0]:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + leftKeyNum + " " + leftKeyName + 
                                  " 发送到 " + rightKeyNum + " " + rightKeyName + " " + str(amountETH) + "ETH  成功")
            else:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + leftKeyNum + " " + leftKeyName + 
                                  " 发送到 " + rightKeyNum + " " + rightKeyName + " " + str(amountETH) + "ETH  失败")
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')
        
# 一对一转账部分资金
    def mfPtoPPortion(self):
        self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + "  把左侧选中账户的指定金额一对一转到右侧选中账户")
        QApplication.processEvents()
        
        global gDict, gDict_2
        
        leftList = self.mfGetLeftKeyList()
        rightList = self.mfGetRightKeyList()
        if len(leftList) != len(rightList):
            QMessageBox.about(self, '提示', '请左右两侧选择相同数量的账户')
            return        

        networkName = self.cbNetwork.currentText()
        w3 = getWeb3HTTPProvider(networkName)
        chainID = getChainID(networkName)

        for left, right in zip(leftList, rightList):
            leftKeyNum = left.split(':')[0].rstrip()
            leftKeyName = left.split(':')[1].rstrip()
            leftPrivateKey = gDict['keys'][leftKeyNum]['privateKey']
            rightKeyNum = right.split(':')[0].rstrip()
            rightKeyName = right.split(':')[1].rstrip()
            rightPrivateKey = gDict_2['keys'][rightKeyNum]['privateKey']

            gas_limit = 21000       # 发送以太币所需的标准gas数量
            totalETH = self.dsbValuePtoPPortion.value()
            totalWei = w3.to_wei(totalETH, 'ether')
            amountWei = totalWei - w3.eth.gas_price * gas_limit
            amountETH = w3.from_wei(amountWei, 'ether')

            if amountETH <= 0:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + leftKeyNum + " " + leftKeyName + " 转账金额<=0 跳过此转账")
                QApplication.processEvents()
                continue

            # gas_price gas_limit 参数可以是0, 在函数中 gas_price会自动获取, gas_limit 默认21000
            # transfer_eth返回值是一个元组, 第一个值是bool,表示是否成功.  第二个值是字符串,表示成功或错误的信息
            result = transfer_eth(w3, leftPrivateKey, rightPrivateKey, chainID, amountETH, 0, 0)   
            if result[0]:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + leftKeyNum + " " + leftKeyName + 
                                  " 发送到 " + rightKeyNum + " " + rightKeyName + " " + str(amountETH) + "ETH  成功")
            else:
                self.teLog.append( datetime.datetime.now().strftime("%H:%M:%S  ") + leftKeyNum + " " + leftKeyName + 
                                  " 发送到 " + rightKeyNum + " " + rightKeyName + " " + str(amountETH) + "ETH  失败")
            QApplication.processEvents()

        self.teLog.append( "----------------------------------")
        self.teLog.append( '\n')
        










#主程序入口
if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWin = ETHSwap()
    myWin.show()

    appExit = app.exec_()
    #退出程序之前，保存界面上的设置
    myWin.mfSaveFile()      # 保存打开的km文件
    myWin.mfSaveFile_2()
    # 左侧
    tempDict = { 'filePath':myWin.labelFilePath.text(), 'folderPath':myWin.labelFolderPath.text() }
    saveIniJson = json.dumps( tempDict, indent=4)
    try:
        saveIniFile = open( "./ETHSwap.ini", "w",  encoding="utf-8")
        saveIniFile.write( saveIniJson)
        saveIniFile.close()
    except:
        QMessageBox.about( myWin, "提示", "保存配置文件ETHSwap.ini失败")
    # 右侧
    tempDict_2 = { 'filePath':myWin.labelFilePath_2.text(), 'folderPath':myWin.labelFolderPath_2.text() }
    saveIniJson_2 = json.dumps( tempDict_2, indent=4)
    try:
        saveIniFile_2 = open( "./ETHSwap_2.ini", "w",  encoding="utf-8")
        saveIniFile_2.write( saveIniJson_2)
        saveIniFile_2.close()
    except:
        QMessageBox.about( myWin, "提示", "保存配置文件ETHSwap_2.ini失败")

    

    sys.exit( appExit)
