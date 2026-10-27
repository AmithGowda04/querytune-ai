-- AdventureWorks-STYLE schema, written by hand for this project (simplified;
-- NOT Microsoft's original DDL). T-SQL. All corpus queries target this schema.
-- Deliberate features: nullable columns, VARCHAR vs NVARCHAR, composite PK,
-- non-unique join keys, DATE vs DATETIME.

CREATE TABLE dbo.Territory (
    TerritoryID  INT          NOT NULL PRIMARY KEY,
    Name         NVARCHAR(50) NOT NULL,
    CountryCode  CHAR(2)      NOT NULL
);

CREATE TABLE dbo.Customer (
    CustomerID   INT          NOT NULL PRIMARY KEY,
    FirstName    NVARCHAR(50) NOT NULL,
    LastName     NVARCHAR(50) NOT NULL,
    Email        VARCHAR(100) NULL,
    Phone        VARCHAR(20)  NULL,
    TerritoryID  INT          NULL REFERENCES dbo.Territory(TerritoryID),
    CreatedDate  DATETIME     NOT NULL
);

CREATE TABLE dbo.Department (
    DepartmentID INT          NOT NULL PRIMARY KEY,
    Name         NVARCHAR(50) NOT NULL
);

CREATE TABLE dbo.Employee (
    EmployeeID   INT           NOT NULL PRIMARY KEY,
    FullName     NVARCHAR(100) NOT NULL,
    DepartmentID INT           NOT NULL REFERENCES dbo.Department(DepartmentID),
    ManagerID    INT           NULL REFERENCES dbo.Employee(EmployeeID),
    HireDate     DATE          NOT NULL
);

CREATE TABLE dbo.ProductSubcategory (
    SubcategoryID INT          NOT NULL PRIMARY KEY,
    Name          NVARCHAR(50) NOT NULL
);

CREATE TABLE dbo.Product (
    ProductID        INT           NOT NULL PRIMARY KEY,
    Name             NVARCHAR(100) NOT NULL,
    ProductNumber    VARCHAR(25)   NOT NULL UNIQUE,
    Color            VARCHAR(15)   NULL,
    ListPrice        DECIMAL(10,2) NOT NULL,
    SubcategoryID    INT           NULL REFERENCES dbo.ProductSubcategory(SubcategoryID),
    DiscontinuedDate DATETIME      NULL
);

CREATE TABLE dbo.SalesOrderHeader (
    OrderID       INT           NOT NULL PRIMARY KEY,
    CustomerID    INT           NOT NULL REFERENCES dbo.Customer(CustomerID),
    OrderDate     DATETIME      NOT NULL,
    ShipDate      DATETIME      NULL,
    Status        TINYINT       NOT NULL,
    SalesPersonID INT           NULL REFERENCES dbo.Employee(EmployeeID),
    TotalDue      DECIMAL(12,2) NOT NULL
);

CREATE TABLE dbo.SalesOrderDetail (
    OrderID    INT           NOT NULL REFERENCES dbo.SalesOrderHeader(OrderID),
    LineNumber INT           NOT NULL,
    ProductID  INT           NOT NULL REFERENCES dbo.Product(ProductID),
    Quantity   INT           NOT NULL,
    UnitPrice  DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (OrderID, LineNumber)
);
