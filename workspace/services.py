from dataclasses import dataclass

from utils.logging import Logger

from processing.cleansing import DataCleaner
from processing.headers import HeaderDetector
from processing.loading import FileLoader
from processing.transforms import DomainTransforms
from processing.packaging import ZipEncryptor
from processing.repos.seeds_repo import SeedsRepository
from processing.repos.postcodes_repo import PostcodesRepository
from processing.repos.ucids_repo import UcidsRepository
from processing.repos.return_addresses_repo import ReturnAddressesRepository
from processing.repos.ecom_services_repo import EcomServicesRepository
from processing.repos.mailsort_services_repo import MailsortServicesRepository
from processing.repos.login_repo import LoginRepository
from gui.password_broker import PasswordBroker

@dataclass
class Services:
    logger: Logger
    password_broker: PasswordBroker
    cleaner: DataCleaner
    headers: HeaderDetector
    transforms: DomainTransforms
    packager: ZipEncryptor
    seeds_repo: SeedsRepository
    postcodes_repo: PostcodesRepository
    ucids_repo: UcidsRepository
    return_addresses_repo: ReturnAddressesRepository
    mailsort_services_repo: MailsortServicesRepository
    ecom_services_repo: EcomServicesRepository
    mailmark_logins_repo: LoginRepository
    mixed_weight_logins_repo: LoginRepository
    loader: FileLoader

def build_services(window) -> Services:
    logger = Logger(lambda msg, _c=None: window.log_signal.emit(msg))

    password_broker = PasswordBroker(window)

    cleaner = DataCleaner(logger)
    headers = HeaderDetector(logger)
    transforms = DomainTransforms()
    packager = ZipEncryptor()
    seeds_repo = SeedsRepository()
    postcodes_repo = PostcodesRepository()
    ucids_repo = UcidsRepository()
    return_addresses_repo = ReturnAddressesRepository()
    mailsort_services_repo = MailsortServicesRepository()
    ecom_services_repo = EcomServicesRepository()
    mailmark_logins_repo = LoginRepository(db_filename="mailmark_logins.db", table_name="mailmark_logins")
    mixed_weight_logins_repo = LoginRepository(db_filename="mixed_weight_logins.db", table_name="mixed_weight_logins")

    loader = FileLoader(
        header_detector=headers,
        cleaner=cleaner,
        logger=logger,
        password_callback=password_broker.get_password)

    return Services(
        logger=logger,
        password_broker=password_broker,
        cleaner=cleaner,
        headers=headers,
        transforms=transforms,
        packager=packager,
        seeds_repo=seeds_repo,
        postcodes_repo=postcodes_repo,
        ucids_repo=ucids_repo,
        return_addresses_repo=return_addresses_repo,
        mailsort_services_repo=mailsort_services_repo,
        ecom_services_repo=ecom_services_repo,
        mailmark_logins_repo=mailmark_logins_repo,
        mixed_weight_logins_repo=mixed_weight_logins_repo,
        loader=loader)