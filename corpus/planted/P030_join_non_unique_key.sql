SELECT c.CustomerID, e.EmployeeID FROM dbo.Customer c JOIN dbo.Employee e ON c.TerritoryID = e.DepartmentID;
